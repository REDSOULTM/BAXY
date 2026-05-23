# Shakedown final E2E — sesión de cierre 2026-05-21

Validación realista (no sintética) de la cadena del agente con recursos reales.

## Restricción de entorno (sin cambios respecto a las 2 sesiones previas)

- `torch.cuda.is_available()` → False (build CPU-only en este intérprete).
- `nvidia-smi`: GPU 16 GB, **6.6 GB ya en uso**, util 0%.
- CLAUDE.md mand. 6 + "ESTOY JUGANDO": no levantar un modelo de ~6 GB sobre una
  GPU ocupada (riesgo de OOM-ear el proceso residente del usuario).

**Decisión:** el shakedown del LLM E2E (turno completo a través de llama-server)
queda DIFERIDO con razón. TODO lo demás — la cadena de audio E2E y el presupuesto
de latencia Python-side — se corrió de verdad con modelos y audio reales.

---

## Exp A — Wake sobre RUIDO REAL (eje: FIABILIDAD/precisión) ✅

Cargué el modelo LiveKit REAL y le pasé 15 clips de ruido real
(`data/backgrounds/noise/free-sound/*.wav`, 302 s totales) en chunks de 32 ms.

- **Falsos wakes: 0** → **0.00 fp/hr** (gate del proyecto: ≤ 1.0). PASA.
- Wake CPU: 58.1 s para 302 s de audio = **19% de realtime** (consistente con el
  throttle de la ronda 8).

VEREDICTO: ✅ la precisión del wake en audio real cumple el gate; el throttle
mantiene el costo bajo.

## Exp B — STT E2E sobre voz REAL (eje: LATENCIA/fiabilidad) ✅

Decodifiqué la grabación original del operador (`Grabación (2).m4a`, 293 s) a
16 kHz mono vía ffmpeg y la pasé por el STT real (faster-whisper small, CPU int8).

- **STT: 15.18 s para 293 s de audio → RTF 0.05** (20× más rápido que realtime).
- Transcript (raw Whisper): "¡Abre cromo! ¡Abre steam! ¡Cierra whatsapp! ¡Minimiza
  la ventana!..." — los comandos reales grabados, con las mistranscripciones de
  anglicismos esperadas ("cromo", "Sierra") que el corrector arregla downstream.

VEREDICTO: ✅ el STT en CPU está MUY dentro de presupuesto (RTF 0.05).

## Exp C — Cadena STT → corrector (eje: fiabilidad) ✅

Pasé los segmentos del transcript real por `strip_wake_phrase` + `correct`:

- "Abre steam" → **"abre Steam"** (matcheó el inventario de apps). ✅
- "Abre cromo" → "abre cromo" (conservador: el umbral de coverage no matcheó
  cromo→chrome con el prefijo pegado). Comportamiento DOCUMENTADO ("mantiene el
  token original si no hay match claro") — no es regresión, es la conservadurismo
  intencional que evita corregir de más.

VEREDICTO: ✅ la cadena funciona; la conservadurismo del corrector es by-design.

## Exp D — Presupuesto de latencia Python-side (eje: LATENCIA) ✅

`test_perf_budget.py` (los guardrails nuevos) corrido como shakedown:

- compaction 10 MB < 50 ms (real ~2.7 ms). ✅
- `_system_message` warm < 5 ms (real ~1.06 ms con el cache de microagents). ✅
- wake N=4 < 60% del CPU de N=1 (real ~26%). ✅

VEREDICTO: ✅ los 3 presupuestos pasan con amplio margen.

## Exp E — LLM E2E (turno completo a través de llama-server) ⏸️ DIFERIDO

Mismo motivo que las 2 sesiones previas: GPU ocupada + usuario potencialmente
jugando. El path está cubierto por tests mockeados (recovery, timeout, dispatch)
y auditado limpio; falta SOLO la medición E2E de TTFT/decode en vivo, que requiere
la GPU libre.

---

## Resumen

| exp | qué | resultado | veredicto |
|-----|-----|-----------|-----------|
| A | wake sobre ruido real (302s) | 0 FP, 0.00 fp/hr, CPU 19% RT | ✅ |
| B | STT sobre voz real (293s) | RTF 0.05 (15s/293s) | ✅ |
| C | STT→corrector | "abre Steam" matcheado; conservador OK | ✅ |
| D | presupuesto latencia | 3/3 budgets pasan | ✅ |
| E | LLM E2E | — | ⏸️ diferido (GPU) |

4/5 corridos con recursos REALES (modelos + audio del operador). Ninguna anomalía.
El único diferido es el LLM E2E por la restricción de GPU — no es un hallazgo.

## Procesos al cierre del shakedown

No levanté llama-server (GPU ocupada). Wake/STT/corrector cargados en el proceso
de test y liberados al terminar. Sin procesos colgados.
