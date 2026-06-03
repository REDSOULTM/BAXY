# `gemma4_agent` — Production-Ready Acceptance Gate

> Esta es la regla del juego. Cuando los 5 thresholds están en
> verde simultáneamente en un commit, `gemma4_agent` se considera
> production-ready para un usuario. No antes, no en base a
> "sensación", no en base a "26 sprints sin regresiones". Estos 5
> números o nada.
>
> Origen: investigación post-Sprint P 2026-05-18.

## Los 5 thresholds

| # | Métrica | Threshold | Cómo se mide | Estado actual |
|---|---|---|---|---|
| 1 | **Wake recall** | ≥70% en `testaudio_v2.wav` (nativo WAV, no m4a) | `bench.py` cuenta wakes detectados vs wakes esperados (anotados en `testaudio_v2_expected.json`) | ❌ 25% en `Grabación (2).m4a`, sin medición en v2 |
| 2 | **Wake false-positive rate** | ≤1 FP / hora en 30min de audio idle | `bench.py` corre Vosk sobre `testaudio_idle.wav` (silencio + ruido de fondo, sin wake intencional) y cuenta fires | ❌ Sin medición |
| 3 | **STT WER medio** | <0.20 vs Whisper-large-v3 ground truth sobre `testaudio_v2.wav` | `bench.py` corre small vs large, computa WER con `jiwer` (Sprint N infra) | ❌ Sprint N reportó WER medio ~0.57 en `Grabación (2)` |
| 4 | **STT latency p95** | ≤1.2s para clips ≤3s, GPU disponible | `bench.py` mide `_transcribe_buffer` sobre clips sintetizados; p95 sobre 20 iteraciones por clip | ❌ Sprint N corrió en CPU/int8 (DLL missing) — invalida medición |
| 5 | **Voice end-to-end p95** | ≤5s wake→TTS start, sesión real con 20 comandos diversos | Sesión manual con 20 turnos, recorder anota timings en manifest; bench parsea | ❌ Sin medición; budget operator memory dice 4-5s |

## Métricas auxiliares (NO bloqueantes, solo informativas)

- **Filter false-positive rate**: % turns con `whisper_raw_text`
  no-vacío PERO `whisper_transcription` null en manifest. Si >20%
  sostenido en sesiones de uso real → calibrar filtros (Sprint O).
- **Silent fallback count per session**: trace events
  `silent_fallback`. Si ≥1 por sesión → V (except triage) sube
  prioridad.
- **TTS finish-to-next-wake median**: silencio post-reply.
  Indicador UX. No threshold, solo telemetry.

## Decisión

Los 5 thresholds se evalúan TODOS antes de declarar
production-ready. **AND, no OR**.

- 4/5 verde + 1 rojo → NO production-ready. Reportar cuál falla y
  arrancar sprint específico.
- 5/5 verde EN UN MISMO COMMIT → production-ready.
- Cualquier commit posterior que mueva alguno de los 5 a rojo →
  regresión bloqueante. Rollback o fix antes de mergear más.

## Cómo se corre

```bash
# Modo full (todos los thresholds, 5min en hardware operador):
python scripts/bench.py

# Modo CI (rápido, solo los thresholds que no requieren GPU/audio fresh):
python scripts/bench.py --ci

# Modo single (un threshold específico):
python scripts/bench.py --threshold wake_recall
```

Output: `bench_results/<YYYYMMDD_HHMMSS>.json` + `.md`.

## Audios requeridos

| Archivo | Cómo generar | Cuándo |
|---|---|---|
| `testaudio_v2.wav` | Operador graba 20-30 comandos diversos en WAV nativo (Audacity / Sound Recorder Windows). No m4a, sin compression. ES + EN mix, normal/fast/whispered. | Antes de R2 |
| `testaudio_v2_expected.json` | Manifest manual: por cada timestamp de wake intencional, marca `expected_wake: true`. Resto: `false`. | Operador lo arma post-grabación |
| `testaudio_idle.wav` | 30min de audio de la habitación SIN intentos de wake. Ruido base. | Antes del threshold #2 |

Si los audios no existen al correr `bench.py`, el harness usa
`Grabación (2).wav` como fallback degradado y marca los
thresholds como `SKIPPED — missing reference audio`. No
falla; reporta limpio.

## Política de re-medición

- Después de cada sprint que toque el voice pipeline, correr
  `bench.py` y commitear el resultado en `bench_results/`.
- Comparar contra el último resultado del previous sprint.
- Si alguno de los 5 retrocedió ≥10%, rollback del commit que
  lo introdujo (excepto si fue intencional + documentado).

## Lo que NO está acá (intencional)

- Multi-operator (X) y i18n (Y) NO son thresholds. Son
  capabilities que se evalúan recién cuando aparece la demanda.
  El informe lo aclaró.
- Tests unitarios verdes NO es threshold (es prerequisito básico).
- Cobertura de tools (65/65 con verifier) NO es threshold —
  ningún usuario va a sentir que `verify_xyz` no existe; los
  van a sentir cuando el flujo se rompa.

---
