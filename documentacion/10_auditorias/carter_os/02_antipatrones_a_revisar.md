# 02 — Anti-patrones que Carter pagó caro (verificar que NO los tenemos)

`11_lecciones_v1_a_v4.md` §3 lista los errores que costaron generaciones enteras.
Para CADA uno: ¿lo tenemos nosotros? Esto es lo más valioso de la auditoría —
aprender de errores ajenos sin pagarlos.

| Anti-patrón de Carter | Síntoma que causó | ¿Lo tenemos? | Acción |
|---|---|---|---|
| **3.5 History dinámica invalida el KV cache** — system_msg con history+memory+bloques cambia cada turn → re-prefill 1-3s | Latencia 1-tool 16s en bench vs 4.26s puro (+10s overhead) | **PARCIAL — RIESGO REAL.** Nuestro `_system_message` inyecta memoria por turno. PERO: (a) medimos que el prefix-cache de b9090 SÍ funciona, (b) el context_router (inv 4) ya reduce historia, (c) la memoria en capas (inv 2) ahora manda menos tokens. | **REVISAR**: confirmar que el prefijo estable (rules+tools) va ANTES de lo variable (memoria/historia), no entremezclado. Ver 03. |
| **3.6 Retrieval per-turn cambia el set de tools** → catalog distinto cada turn rompe cache | Modelo ve "tools nuevas" cada turn | **A VERIFICAR.** Nuestro router elige subset por turno (top-K 4-6). ¿Eso cambia el catalog enviado y rompe cache? | **MEDIR**: ¿el orden/contenido de `tools=[]` varía turn-a-turn en una misma sesión? Si sí, evaluar core-set estable (lo medimos y dio 2× peor una vez — re-medir con el layout correcto). |
| **3.4 / 3.10 8 capas de post-LLM rewriter distorsionan** | INFORME_NOCTURNO: "respuestas pobres" | **VERIFICADO: BAJO RIESGO.** Tenemos ~3-4 guards (reply_validator, _chaining_nudge, _autorepair_path_from_search, honesty), NO 8 capas. Y mayormente ANOTAN/reparan, no reescriben el texto del usuario. | Mantener bajo control: no agregar rewriters de contenido. Los actuales están OK. |
| **3.1 Acumulación sin remoción** — cada capa se agrega para 1 caso, nadie quita la anterior | agent.py drift +250% | **RIESGO LATENTE.** Acabamos de agregar 9 features (8 inv + ducking). Sano hoy, pero el patrón es el mismo. | **DISCIPLINA**: cada feature con gate + medible. Ya lo hacemos. Revisar en 1 mes si alguna quedó sin justificar. |
| **3.2 Routers compitiendo** (3 routers en serie + 3 `select_profile`) | Solapamiento conceptual | **PROBABLE QUE NO.** Tenemos semantic_router → intent_router → abstain_head → planner (pipeline, no competencia). Pero hay context_router + command_splitter nuevos. | **VERIFICAR**: que cada router tenga responsabilidad disjunta (intención vs deixis vs multi-intent), no que dos decidan lo mismo. |
| **3.3 Per-app hardcodes** (`_WEB_APP_URLS`, `_DEEPLINK_APPS`, `_NATIVE_APPS`) violan universalidad | Funciona en bench, rompe apps no listadas | **VERIFICADO: NO los tenemos.** Grep no encontró dicts app→url hardcoded. Estamos MEJOR que Carter v4 acá. | Ninguna. ✅ |
| **3.8 Bench mide estructura, no calidad** ("PASS estructural / FAIL semántico") | Saludo+acción concatenados, alucinaciones que "pasan" | **APLICA.** Nuestro smoke_e2e mide estructura. | **NOTA**: tener presente que un PASS de smoke no garantiza calidad. Por eso la cacería de fallos en vivo rinde. |
| **3.9 Cambiar varias cosas sin medir** → -13 pts en Carter v4 | Refactor simultáneo | **NO** (disciplina actual = un cambio/commit + gate). Mantener. | OK |

## Los 2 riesgos REALES a accionar (los demás son "verificar/disciplina")

### Riesgo A — Layout del prompt (anti-patrón 3.5 + 3.6)
Es el de mayor impacto medido por Carter (+10s/turn). Nosotros lo mitigamos en
parte (cache-reuse funciona, context_router, memoria en capas) pero **nunca
auditamos el ORDEN de ensamblado** del system_msg. Si lo variable (memoria,
microagents que dependen del turno) está ANTES de lo estable, fragmenta el cache
desde ese punto.

**Test concreto:** loguear el prompt de 2 turnos consecutivos en una sesión y
hacer diff. Lo ideal: que difieran SOLO al final (cola de historia + user). Si
difieren en el medio (memoria/tools), hay fragmentación.

### Riesgo B — Catalog de tools variable (3.6)
Nuestro router manda subset por turno. Si "abrí Spotify" y luego "subí el volumen"
mandan catalogs distintos, el cache de tools se rompe cada turn. Carter migró a
**catalog estable por sesión** (16 composite fijas). Nosotros tenemos 65 tools y
top-K dinámico — el trade-off distractor-cost vs cache-stability hay que MEDIRLO
en nuestro stack (ya lo intentamos una vez con resultado ambiguo).

> Ambos riesgos se atacan con el mismo experimento: **instrumentar el diff de
> prompt entre turnos** y medir `prompt_n` (tokens reevaluados) en `/timings`.
> Es barato y da el número que decide si vale reordenar.
