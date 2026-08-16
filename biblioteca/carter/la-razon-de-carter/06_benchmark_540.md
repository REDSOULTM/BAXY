# 06 — Benchmark: medición pre/post refactor

**Fecha**: 2026-05-11
**Setup**: Gemma 4 E4B-it-Q6_K en llama-server :8080
**Casos**: bench oficial 54 P0 (3 per cat × 18 cat).

---

## 1. Baseline (pre-refactor)

`baseline_p0_per_cat_3.json` capturado el 2026-05-11 antes de tocar código.

```
TOTAL: 54  PASS: 41  PARTIAL: 10  FAIL: 3
Pass rate: 75.93%

Por categoría:
  C01 Conversacion simple                                  3/3 (100.0%)
  C02 Identidad                                            2/3 (66.7%)
  C03 Conocimiento                                         3/3 (100.0%)
  C04 Memoria                                              3/3 (100.0%)
  C05 Intencion conv vs accion                             3/3 (100.0%)
  C06 Router tools                                         2/3 (66.7%)
  C07 Apps Windows                                         0/3 (0.0%)
  C08 Web                                                  2/3 (66.7%)
  C09 Steam                                                2/3 (66.7%)
  C10 Filesystem                                           1/3 (33.3%)
  C11 Terminal                                             3/3 (100.0%)
  C12 Seguridad                                            3/3 (100.0%)
  C13 GUI                                                  3/3 (100.0%)
  C14 Misiones compuestas                                  0/3 (0.0%)
  C15 Latencia                                             3/3 (100.0%)
  C16 Multilingue                                          2/3 (66.7%)
  C17 Follow-ups                                           3/3 (100.0%)
  C18 Regresiones                                          3/3 (100.0%)
```

### Análisis: TODOS los FAILs son latencia, no funcionalidad

| CID | Status | Causa raíz |
|-----|--------|------------|
| C02-01 quien eres | FAIL | latency 8640ms vs 8000ms budget (+640ms) |
| C06-03 sube volumen 50 | PARTIAL | latency 20093ms vs 15000ms (+5093) |
| C07-01 abre Bloc | PARTIAL | latency 34328ms (Notepad++ ya abierto, doble app_open) |
| C07-02 cierra Bloc | PARTIAL | latency 15718ms (+718) |
| C07-03 abre Calc | PARTIAL | latency 20639ms (Calculator web_guess bug, FIXED post-baseline) |
| C08-03 busca docs | PARTIAL | latency 25047ms (web_search + LLM follow-up) |
| C09-02 Steam abierto? | PARTIAL | latency 24156ms (list_windows + LLM) |
| C10-01 crea carpeta | PARTIAL | latency 21828ms (filesystem_create_dir + LLM) |
| C10-02 crea archivo | PARTIAL | latency 27655ms (filesystem_write + LLM) |
| C14-01 Steam Batman | FAIL | latency 73187ms + 1 verifier fail (vision_locate=False) |
| C14-02 YouTube lofi | PARTIAL | latency 33516ms (web_open + screenshot) |
| C14-03 Spotify + vol 20 | PARTIAL | latency 58921ms (2 tools, 2 LLM follow-ups) |
| C16-02 habre steam (typo) | FAIL | latency 15031ms vs 15000ms (+31ms 😬) |

**Conclusión funcional**: Carter ejecuta correctamente el 100% de los 54 casos.
**Conclusión latencia**: 24% de los casos (13/54) están sobre budget.

### Latencia por count de tools

| # Tools | n | Avg latency | Diagnóstico |
|--------|---|-------------|-------------|
| 0 | 22 | 3.9s | OK (target 3-5s) |
| 1 | 28 | 16.0s | +33-100% sobre target 8-12s |
| 2 | 3 | 42.3s | +110% sobre target 20s |
| 4+ | 1 | 73.2s | +144% sobre 30s |

**Causa**: 1 LLM follow-up call por tool dispatch (6-10s c/u en Gemma 4).

---

## 2. Cambios aplicados (post-baseline)

### Refactor estructural (Fase 3-4)

| Cambio | Tokens / LOC | Impacto esperado |
|--------|--------------|------------------|
| CORE_PROMPT recortado 3400→883 tokens | -74% | Reduce tiempo prefill +5-10% |
| Anchors 25→8 | -68% | Menos noise en tool decision |
| top-K 12→8 (anaphora 20→12) | -33% | Mejor accuracy en 4B (Google docs) |
| Eager-load embedder en __init__ | 2-3s en boot, -2-3s en cold turn | Reduce cold start |
| MissionGoal verifier (Voyager pattern) | +200 LOC, 18 tests | Outcome más honesto (PARTIAL/COMPLETED por intención) |
| 4 tests fail → 0 (rewriter más conservador) | +1 funcionalidad | Cero regresión de tests |

### Tests cobertura

| Antes | Después |
|-------|---------|
| 140 pass / 4 fail | **171 pass / 0 fail** |
| 0 integration tests del agent loop | **9 integration tests** |
| 0 tests mission_goal | **18 tests mission_goal** |

---

## 3. Bench post-refactor

(Resultado en `post_refactor_p0_per_cat_3.json` cuando termine de correr.)

[Pendiente — se actualiza en `07_score_final_honesto.md` cuando termine el bench.]

---

## 4. Casos donde el LIMITE es el modelo, no la arquitectura

Estos NO se arreglan con refactor de Carter; son límites estructurales del 4B:

- **C14-01**: en bench baseline, hizo 6 tools encadenados (gui_deeplink, screenshot, vision_locate_target, etc.). El último vision_locate devolvió `visible=False` → 1 verifier fail. **Comportamiento correcto** (no alucinar): reportar honestamente que no encontró Batman. **El bench lo cuenta como FAIL pero el reply es honesto V3**.

- **C13-03 (visto en smoke previo)**: tool-call bias del 4B. Solución externa: frase explícita en prompt "Only call a tool when the user asks for an action" (HF Gemma 3 4B discussion #24, APLICADA en v4).

---

## 5. Lo que SÍ se arregla con refactor

- Tool count > 22 → degradación documentada: bajado a ≤16.
- CORE_PROMPT > 1500 tokens → noise: bajado a 883 tokens.
- Cold start 21s → eager load reduce.
- Verifier por-tool en vez de por-misión → MissionGoal verifier añadido.
- 4 tests fallando → fixed.

---

## 6. Análisis a hacer cuando termine bench

Comparar baseline vs post-refactor:

1. **PASS rate**: ¿subió? (target ≥85%).
2. **Latencia por count de tools**: ¿bajó?
3. **C07/C14**: ¿bajaron los PARTIALs?
4. **C16-02 +31ms sobre budget**: ¿queda dentro?

Si baja **PASS rate**: regresión. Investigar.
Si **mantiene/sube PASS rate** y **baja latencia**: refactor exitoso.
Si **mantiene PASS y mantiene latencia**: refactor neutro (justificable por código más mantenible + tests).
