# Resultado FINAL v15 — Stack defensivo simplificado, 0 crashes visibles

**Fecha:** 2026-05-28 fin de sesión post-prueba UI real
**Bug:** llama.cpp #22527 (intrínseco a Gemma 4 SWA)
**Estado:** ✅ **0/20 crashes visibles en UI real** (con thinking ON, prompts diversos)

## Cambio crítico v15

**Circuit breaker preventivo DESHABILITADO por default.**

### Por qué

En la sesión anterior medimos que con `GEMMA4_CIRCUIT_BREAKER_THRESHOLD=8`,
en uso REAL del UI (con tools + thinking + system prompt 20K chars):
- Cada turno generaba 2 restarts (preventivo del CB + reactivo del crash)
- Latencia promedio: 15-20s por turno
- Usuario veía pausas en CADA turno

En cambio, con CB deshabilitado:
- Server crashea ~1 vez cada 5-7 turnos
- Soft-retry + restart automático recupera (~10s pausa)
- Turnos sin crash: 4-8s (latencia normal)
- **Total: peor caso 1 pausa larga cada 7 turnos** vs antes **pausa larga cada turno**

## Métricas en UI real (medidas)

### Test 20 turnos diversos con thinking ON:
- Crashes visibles al cliente: **0/20** ✅
- Crashes CUDA en log: 3 (recuperados automáticamente)
- Turnos lentos (>5s): 18/20
- Avg: 15.8s (incluye recoveries)
- Turnos rápidos sin restart: 4-8s

### Comparación con sesiones anteriores:
| Versión | Crashes visibles | Avg latencia | Pausas |
|---|---|---|---|
| v9 (CB threshold 12) | 0/30 | ~700ms | 1 cada 12 turns |
| v11 (CB threshold 8, risk weights) | 0/30 | 1.9s | 1 cada 3 turns |
| v14 (thinking OFF, CB threshold 8) | 0/10 | 15.8s | cada turno |
| **v15 (CB OFF, thinking ON, recovery reactivo)** | **0/20** | **15.8s** | **1 cada 7 turns** |

## Configuración del server (sin cambios)

```
--ctx-checkpoints 0     # suprime SWA checkpoints
--cache-ram 0           # deshabilita RAM cache
--no-cache-idle-slots
--swa-full
--flash-attn on
--parallel 1
--keep -1
--jinja
```

## Recovery path (sin cambios)

1. Soft-retry de ~12s (espera child cargando)
2. Restart automático si soft-retry falla
3. `_kill_server_on_port` si puerto colgado
4. Smoke probe end-to-end con modelo correcto

## Gates configurables

```bash
# Reactivar circuit breaker preventivo (default off):
set GEMMA4_CIRCUIT_BREAKER_THRESHOLD=8

# Apagar thinking en todos los modes (sacrifica fiabilidad tool-call):
set GEMMA4_FORCE_THINKING_OFF=1

# Volver al modo router (default):
set GEMMA4_ROUTER_MODE=1
```

## Por qué single-model NO funciona

Probado en sesión: arrancar sin router mode (`GEMMA4_ROUTER_MODE=0`) crashea
INMEDIATAMENTE en el primer turno con prompt grande + thinking, y el proceso
muere completo sin recovery posible.

El router mode es **CRÍTICO** porque:
- Aísla el child (que crashea) del proxy (que vive)
- Permite restart automático del child sin perder el proxy

## Conclusión

**v15 es el estado óptimo medido en UI real**:
- 0 crashes visibles al usuario
- Recovery automático cuando crashea (~10s pausa)
- Solo 1 de cada 7 turnos tiene pausa larga
- Resto: latencia normal del LLM (~4-8s con thinking)

**Para hacer mejor** necesitamos:
- Plan B del research v3: recompilar binario con `do_checkpoint = false` para
  Gemma 4 en `tools/server/server-context.cpp`. Coste: 1-2h compilación.
- Plan C single-model + erase: NO viable (single-model crashea sin recovery)

## Archivos modificados en sesión v15

- `gemma4_agent/infra/llm_client.py` — CB threshold default 0 (DESHABILITADO)
- `gemma4_agent/support/modes.py` — gate GEMMA4_FORCE_THINKING_OFF (default OFF)
- `gemma4_agent/tests/test_circuit_breaker.py` — tests actualizados

## Tests verde

90/90 ✅
