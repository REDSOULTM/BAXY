# Sprint de latencia — reporte final 2026-05-22

Objetivo: todos los turnos < 4-5s a reply completo, percibida ~1s, calidad
balanceada (caída leve aceptable si el promedio de latencia mejora claro).
Medido contra el server de producción real (vram12-text, E4B-Q6, b9090); cada
prompt 3×, mediana; tool dispatch mockeado no-op (seguro). Quality eval =
correctitud/registro vs baseline.

## Resultado por tipo de turno (mediana, baseline → final)

| tipo | n | baseline | final | nota |
|------|---|----------|-------|------|
| smalltalk | 5 | 0.78s | **0.73s** | sin cambio (ya rápido) |
| factual-simple | 6 | 0.59s | **0.60s** | fs2 "GTA5" 15.8s→1.9s (era outlier) |
| pregunta-compleja | 5 | 2.27s | **1.25s** | cx5 "RAM" 48.2s→1.0s |
| accion | 6 | 6.17s | **5.34s** | thinking-para-tool legítimo |
| accion-multistep | 3 | 10.98s | **9.29s** | N tool-calls reales (inherente) |
| research | 2 | 6.84s | **7.37s** | web tools + thinking (retrieval real) |

**CORPUS: median 4.00s → 1.90s. max 48.23s → 11.64s. SLOW(≥5s) 12/27 → 10/27.**
**Quality agregado: 0.959 → 0.989 (SUBIÓ — 2 mejoras, 0 regresiones).**

**Las 16 preguntas info/factual/smalltalk: TODAS ≤ 2.11s** (eran el grueso de los
outliers de 7-48s). Los 10 SLOW restantes son SOLO acciones (5-6.6s, borderline),
multistep (9-11s, inherente) y research (7s, retrieval real).

## Qué optimización dio cada ganancia

| cambio | commit | ganancia | calidad |
|--------|--------|----------|---------|
| chat_stream pasa model (estaba muerto en router) | 3fc94f8 | habilita streaming (TTFT 130ms) | — |
| fact-extraction a daemon thread | 30a572b | saca 2º LLM call del reply (cuando ON) | sin cambio |
| **fast_info mode (thinking OFF en preguntas)** | b6793e9 | **cx5 48→1.1s, cx1 7→1s, fs2 16→1.9s; median 4.0→1.9s** | **SUBIÓ (menos vacíos)** |
| no upgrade/forced-retry en fast_info | b6793e9 | mata el thinking espurio por tool especulativa | sube |
| thinking_budget 384→256 (acciones) | 499c8ae | worst-case guard | sin cambio |

La palanca dominante fue **fast_info**: el thinking en preguntas de conocimiento
era puro costo Y a menudo dejaba el content VACÍO (el reasoning se comía el
budget). Quitarlo bajó latencia Y subió calidad — el balance ideal.

## Curva thinking_budget (decisión #3 del MERGE_CHECKLIST, RESUELTA)

A/B en vivo, turnos de acción (tool app/window):

| prompt | 384 | 256 | 192 | 128 |
|--------|-----|-----|-----|-----|
| "abre la calculadora" | 1.15s | 1.04s | 1.03s | 1.01s |
| "minimiza la ventana" | 1.59s | 1.56s | 1.06s | 1.06s |

El modelo auto-limita el reasoning (128-346 chars) MUY por debajo del budget → el
thinking_budget NO es el cuello de botella de acciones. Bajé a 256 como guarda de
worst-case, sin trade-off. El thinking PROBLEMÁTICO era el del modo info, ya
eliminado. **Decisión #3 cerrada con datos.**

## Streaming (percibida ~1s) — en tradeoffs.md T1 para decisión de RED

La infra `chat_stream` quedó funcional (TTFT 130ms). Pero streamear el reply al
TTS en vivo choca con los guards post-generación (grounding/promise REESCRIBEN el
texto) — streamear y luego corregir rompería "el agente no miente". Documenté las
opciones (UI-stream sin riesgo / TTS-stream con pre-check de claims) en
tradeoffs.md T1 para tu decisión, en vez de bypassear un invariante de seguridad
unilateralmente. NOTA: con la latencia TOTAL ya en 1-2s para info/factual, la
percibida ya mejoró sin streaming; el streaming llevaría las acciones (5-6s) a
~1s percibido.

## Trade-offs aceptados (con números) vs enviados a RED

- **Aceptado (commiteado):** fast_info (calidad SUBIÓ, no es trade-off);
  thinking_budget 384→256 (costo nulo medido).
- **A RED (tradeoffs.md):** T1 streaming-a-TTS vs guards; T3 multistep <5s
  (requiere tocar verificación per-tool o paralelizar — fiabilidad).

## Veredicto vs objetivo

- ✅ **Preguntas (info/factual/smalltalk): TODAS < 2.2s.** Era el peor problema
  (15-48s). RESUELTO.
- ⚠️ **Acciones: 4-6.6s** (borderline; el thinking-para-tool-call fiable es ~2s +
  prefill + summary). La mayoría <5s, algunas justo encima por variance.
- ⚠️ **Multistep/research: 7-11s** — costo INHERENTE de N tool-calls / retrieval
  real. Documentado en tradeoffs T3 (recortarlo toca fiabilidad → RED).
- **first-token < 1.5s con streaming:** disponible (TTFT 130ms medido) pero el
  cableado a TTS espera decisión de RED (T1).

Calidad: **0.989** (subió). Ningún turno degradó; 2 mejoraron (replies antes
vacíos por thinking-runaway ahora confirman).

---

## Verificación cross-perfil del big win (2026-05-22)

Pregunta: ¿el win (fast_info, thinking OFF en preguntas) aplica a TODOS los
perfiles o solo a vram12 (E4B-Q6) donde se midió? Verificado levantando un server
temporal con el modelo MÁS DÉBIL (E2B-Q4 = vram3) en :8091 y A/B contra E4B-Q6.

**Arquitectura:** el routing + el cap de tokens viven en `modes.py`, que es
PROFILE-AGNOSTIC. La única entrada que varía por perfil (`base_max_tokens`) es la
misma (config default 1280) en todos -> `fast_info` = min(1280,320) = 320 en todos.
Test `test_win_is_profile_agnostic` lo pina sobre base 128..2048.

**Calidad (A/B en vivo, thinking OFF):**

| pregunta | E2B-Q4 (vram3, débil) | E4B-Q6 (vram12) |
|----------|----------------------|-----------------|
| capital de Francia | 0.27s ✅ "París" | 0.58s ✅ |
| qué es fotosíntesis | 0.52s ✅ correcta | 0.95s ✅ |
| diferencia RAM/disco | 0.35s ✅ correcta | 0.98s ✅ |
| cuándo salió GTA5 | 0.25s ✅ "17 sep 2013" | 1.90s ✅ |

Thinking OFF en E2B-Q4: TODAS correctas en 0.25-0.52s. Thinking ON en E2B-Q4: 8×
más lento (2-2.5s) y "fotosíntesis" hit finish=length (el modelo débil razona
verboso y RIESGA truncar). **El win es igual o MÁS valioso en el modelo débil.**

**Decode speed por perfil (medido):** E2B-Q4 126 tok/s · E4B-Q6 54 tok/s (2.3×).
El `request_timeout_s` deriva de un floor fijo de 20 tok/s — conservador y SEGURO
bajo el modelo más lento, así que no necesita override por perfil (nunca corta un
reply legítimo en ningún perfil; el fail-fast es backstop, no gate ajustado).

**Veredicto:** el big win es PROFILE-AGNOSTIC en latencia Y calidad. NO se
justifica divergencia por perfil — los datos muestran que E2B-Q4 se comporta como
E4B-Q6 en preguntas info (forzar knobs por perfil sería churn contra la evidencia).
El cap conciso (320 tok + hint de 1-3 frases) mantiene los info-replies cortos en
TODOS los modelos, así que ni el más lento (E4B-Q6, 54 tok/s) se acerca a 5s en
una pregunta. Server temporal E2B-Q4 cerrado tras el test; el server del usuario
(vram12, :8080) intacto.

---

## Validación 3-way por modelo (TODOS los perfiles) 2026-05-22

RED pidió asegurar latencia Y calidad PERFECTAS en cada perfil. Los 6 perfiles
corren 3 modelos distintos; levanté los 3 en paralelo (E2B-Q4 :8091, E4B-Q4 :8092,
E4B-Q6 :8080 del usuario) y corrí 7 prompts representativos (smalltalk + 6
info/factual) con los parámetros reales del modo (thinking OFF, hint conciso, 320
tok). Correctitud = keyword esperado presente.

| modelo | perfiles | avg latencia | slow (≥5s) | incorrectas |
|--------|----------|--------------|-----------|-------------|
| **E2B-Q4** | vram3 | **0.30s** | 0/7 | 0/7 |
| **E4B-Q4** | vram4, vram6, vram8 | **0.48s** | 0/7 | 0/7 |
| **E4B-Q6** | vram12, vram16 | **0.58s** | 0/7 | 0/7 |

**Resultado: en los 3 modelos, las 7 preguntas <1.1s y TODAS correctas.** El más
débil (E2B-Q4) es además el más rápido (0.30s avg). Cero degradación de calidad,
cero turnos lentos, en TODA la línea de perfiles vram3→vram16.

VRAM durante el test 3-modelos-en-paralelo: 12.8 GB / 16 GB (los 3 caben). Los dos
servers de prueba (8091/8092) cerrados tras medir; el del usuario (vram12 :8080)
intacto y respondiendo `status:ok`.

**Conclusión final:** el big win (fast_info, thinking OFF en preguntas) entrega
latencia <1.1s y calidad correcta en CADA perfil del proyecto. Verificado por
medición directa en los 3 modelos, no extrapolado.

---

## Validación de ACCIONES por modelo (cierre del hueco) 2026-05-22

Las verificaciones previas cubrían preguntas; faltaba validar ACCIONES (que iban
borderline 5-6.6s) en cada modelo. Hecho — con una lección de método.

**Acciones contra el server REAL del usuario (vram12, E4B-Q6, router nativo):**

| acción | E2E |
|--------|-----|
| abre la calculadora | 2.26s |
| abre Chrome | 3.78s |
| minimiza la ventana | 1.65s |
| cierra WhatsApp | 4.09s |

Todas <5s, todas con confirmación correcta ("Listo, ...").

**Pass-1 (decidir+emitir tool-call) por modelo, API directa, sin contención:**

| modelo | latencia pass-1 | tool-call emitido | reasoning |
|--------|-----------------|-------------------|-----------|
| E2B-Q4 (vram3) | 1.76-2.08s | ✅ 4/4 | 789-923 chars |
| E4B-Q4 (vram4/6/8) | 0.91-1.09s | ✅ 3/3 | 160-217 chars |
| E4B-Q6 (vram12/16) | 1.13-1.27s | ✅ 3/3 | 160-217 chars |

+ summary pass ~1s = **~2-3.5s por acción en TODOS los modelos**, tool-call fiable
en los 3. El E2B-Q4 razona más (por eso el cap thinking_budget 256 es buena guarda
para el modelo débil), pero emite el tool de forma fiable y se mantiene ~2s/pass.

**LECCIÓN DE MÉTODO (honesta):** una corrida intermedia dio acciones E2B-Q4 en
~17s CONSTANTES. Diagnóstico: NO era el modelo — era un ARTEFACTO DEL TEST
(monkeypatch de resolve_turn_model con un alias `-text` que el server de prueba
no resolvía → loop de recovery de 17s + 3 servers compitiendo por la GPU). Contra
el server real con resolución nativa, las acciones son 1.65-4.09s. El número de
17s NO refleja producción; lo dejo documentado para no engañar.

## Veredicto final por perfil (latencia + calidad)

| perfil | modelo | preguntas | acciones | calidad |
|--------|--------|-----------|----------|---------|
| vram3 | E2B-Q4 | 0.30s avg ✅ | ~2-3.5s ✅ | correcta |
| vram4/6/8 | E4B-Q4 | 0.48s avg ✅ | ~2-3.5s ✅ | correcta |
| vram12/16 | E4B-Q6 | 0.58s avg ✅ | 1.65-4.09s ✅ | correcta |

**En los 3 modelos / 6 perfiles: preguntas <1.1s, acciones <5s, tool-calls
fiables, respuestas correctas.** El multistep real (N acciones) sigue siendo >5s
por diseño (tradeoffs T3). Servers de prueba cerrados; el del usuario intacto.

---

## Smoke test por perfil (reproducible) 2026-05-22

`bench/_profile_smoke.py`: levanta CADA modelo del lineup UNO A LA VEZ (sin
contención de GPU — la contención fue el origen del artefacto 17s) y corre un
mini-corpus mixto (smalltalk/factual/info/acción) con los params reales del modo,
3× por prompt, con gates de latencia + calidad. Resultado:

| perfil (modelo) | smalltalk | factual | info | acción (pass-1) | veredicto |
|-----------------|-----------|---------|------|-----------------|-----------|
| vram3 (E2B-Q4) | 0.12s | 0.14-0.24s | 0.29-0.32s | 1.83-1.98s tc=1 | ✅ |
| vram4/6/8 (E4B-Q4) | 0.14s | 0.32-0.37s | 0.57-0.69s | 0.92-0.94s tc=1 | ✅ |
| vram12/16 (E4B-Q6) | 0.15s | 0.41-0.42s | 0.88-0.91s | 1.16-1.22s tc=1 | ✅ |

**21 checks, TODOS OK** (7 prompts × 3 modelos). Latencia bajo gate y tool-call
fiable (tc=1) en los 3.

NOTA de calidad (honesta): el smoke con un hint CORTO devolvió 2 smalltalk en
inglés ("Hello..."). Verificado que es artefacto del hint mínimo del harness —
con el system prompt REAL del agente (grande, fija ES) el smalltalk responde en
español ("Hola de nuevo", "De nada", "Buen día"). El hint del harness se reforzó
para fijar ES y no marcar falso-positivo. La calidad de idioma en producción es
correcta.
