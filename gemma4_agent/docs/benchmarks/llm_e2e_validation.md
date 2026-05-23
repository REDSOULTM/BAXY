# Validación LLM E2E en vivo — sesión de validación final 2026-05-21

El hueco que las 3 sesiones previas dejaron diferido (GPU). Esta vez había un
**llama-server de producción YA corriendo** en :8080 (router mode, preset
`vram12-text`, E4B-Q6, ctx 16384, --swa-full, --cache-reuse 256, build b9090).
El manager lo detectó como "external" y NO lo tocó (round-11) — validé contra él
sin spawnnear nada (cero riesgo de GPU, cero huérfanos).

> nvidia-smi al arrancar: 6.6 GB en uso = apps de escritorio (dwm, explorer,
> WhatsApp, Edge, Steam Borderless) a 2% util — NO un juego, NO un modelo. Con
> 16 GB totales y E4B-Q6 (~6.5 GB) había ~9.7 GB libres: seguro.

## Exp 1 — TTFT + decode (raw `vram12-text`, sin agente)

| caso | TTFT | decode | total |
|------|------|--------|-------|
| smalltalk "hola" | 22 ms | 55.5 tok/s | 0.22 s |
| pregunta corta (capital) | 73 ms | 53.1 tok/s | 0.21 s |
| respuesta media (think OFF) | 42 ms | 56.6 tok/s | 2.00 s (111 tok) |

- **TTFT 22-73 ms, decode sostenido ~55 tok/s** en E4B-Q6 sobre la 4060 Ti.
- Con thinking ON sin budget, un prompt pelado quema los 512 tok en reasoning y
  devuelve content vacío (finish=length) — por eso el per-mode thinking_budget +
  max_tokens importan. NO es bug; es la razón de la config de modes.py.

## Exp 2 — Turno completo E2E (`Gemma4Agent.run_content`) — HALLAZGO

Acá el E2E reveló lo que el mock no veía. Medición inicial:

| turno | E2E (antes) |
|-------|-------------|
| "¿cuál es la capital de Francia?" | **15.04 s** ❌ |
| "hola" | 11.31 s ❌ |

Diagnóstico (cProfile + traza): el turno hacía 2 calls de LLM. El segundo era el
**forced-tool-retry** disparándose en un turno INFORMATIVO ya respondido en prosa
(el router ofrece web/knowledge/memory en preguntas; el modelo respondió "París"
sin tool, y el retry forzado quemó 512 tok / 11.8 s para no devolver nada).

**Fix (commit a1e0071):** no forzar retry cuando el modelo respondió en prosa Y
todos los domain-tools son de info-retrieval. La retry sigue para acciones.

| turno | E2E (después) |
|-------|---------------|
| "¿cuál es la capital de Francia?" | **3.59 s** ✅ (−76%) |
| "hola" | 1.60 s ✅ |

**Latencia residual conocida (para RED):** turnos donde el modelo elige
pensar+llamar web/knowledge (no determinista) tardan 4-11 s por el thinking
budget de 512 tok a ~55 tok/s. Eso es comportamiento del modelo + tuning de
`thinking_budget`/`max_tokens` para el modo info, NO un bug. Recomendación:
evaluar bajar el thinking_budget del modo info, o decidir que esos turnos
"profundos" pueden exceder el budget de voz. Decisión de producto.

## Exp 3 — Boot (server de producción ya corriendo)

No pude medir cold-boot sin matar el server de producción del usuario (no es
mío). El server activo reporta su config correcta vía /v1/models (preset
vram12-text loaded, los flags de producción). El path de boot está cubierto por
tests mockeados (round 1/6) + el round-11 external-detection que validé hoy en
vivo (el manager respeta el server externo). Cold-boot E2E queda como smoke
opcional cuando no haya un server de producción corriendo.

## Exp 4 — Recovery en vivo (corrupción de experiences.db con server up) ✅

Con un `experience.sqlite` corrupto (1.6 MB de basura, en tmpdir — NO los datos
reales del usuario) Y el server corriendo, corrí un turno:

- **El agente respondió correctamente en 2.50 s** ("La capital de Francia es
  París"). La corrupción NO crasheó el turno — la memoria degrada (record/recall
  best-effort, error swallowed), el turno sobrevive. Invariante de la ronda 4
  confirmado bajo condiciones reales.

## Veredicto por eje

- **ARQUITECTURA:** ✅ el server externo se respeta; recovery contiene la
  corrupción sin tumbar el turno.
- **FIABILIDAD:** ✅ turno sobrevive a DB corrupta; replies correctos.
- **LATENCIA:** ✅ tras el fix, info-turn 15s→3.6s; smalltalk 1.6s. ⚠️ residual
  variable (4-11s) en turnos think+retrieve — tuning de producto, documentado.

## Resumen

| exp | resultado | veredicto |
|-----|-----------|-----------|
| 1 TTFT/decode | 22-73ms / ~55 tok/s | ✅ |
| 2 turno E2E | 15s→3.6s tras fix real | ✅ (1 bug arreglado) |
| 3 boot | server prod ya up; external respetado | ✅ (cold-boot diferido) |
| 4 recovery | turno OK con DB corrupta (2.5s) | ✅ |

El E2E cumplió su propósito: reveló y arregló un bug de latencia real
(forced-retry espurio) que ningún test mockeado veía. Server NO modificado (era
externo); sin procesos colgados por mi parte.

## Fase 3 — Perf budget en vivo (confirmación, sin recalibrar)

`test_perf_budget.py` corrido con modelos reales cargados (la prueba de wake YA
carga el ONNX real; compaction y _system_message son CPU real):

| budget | medido (post-fix) | límite | margen |
|--------|-------------------|--------|--------|
| compaction 10MB | 2.7 ms | 50 ms | 18× |
| _system_message warm | 1.060 ms | 5 ms | 4.7× |
| wake N=4 vs N=1 | ~26% | <60% | holgado |

**Los 3 budgets pasan en vivo con amplio margen — el mock NO subestimaba.** NO
recalibré nada.

**Decisión consciente (anti-flakiness):** NO agregué un assert de latencia de
TURNO contra el server LLM en vivo. La latencia E2E del turno depende del server
y tiene varianza inherente (4-11s en turnos think+retrieve, ver Exp 2). Un assert
así sería FLAKY — exactamente lo que la Fase 2 enseña a evitar. El budget se
mantiene sobre los costos CPU-side DETERMINISTAS; los números E2E del turno quedan
DOCUMENTADOS acá, no como un test no-determinista. Si RED quiere un gate E2E, que
sea un smoke manual/CI con tolerancia amplia y skip-if-no-server.
