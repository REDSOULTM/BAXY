# HOTFIX 2026-05-17 (T) — Session report tool

> Sprint chico, alto ROI. Sprint Q.0 desbloqueó `stt_latency_p95`
> (PASS 0.062s). El siguiente bloqueo del bench es
> `voice_e2e_p95` que está SKIPPED esperando
> `--session-jsonl`. Pero también: cada sesión real grabada por
> `VoiceRecorder` (~/.gemma4/recordings/<session>/manifest.jsonl)
> tiene 8+ campos útiles por turno que hoy nadie lee.
>
> Sprint T construye **un solo tool reader** que:
>   1. Lee un manifest.jsonl y produce un reporte humano + JSON.
>   2. Funciona como la fuente única para `--session-jsonl` del
>      bench (compatibilidad).
>   3. Agrega métricas que los próximos sprints (R2, O, U) van a
>      necesitar para calibrar contra sesiones reales.

---

## Contexto

`gemma4_agent/voice/recorder.py` ya emite por turno
(`finish_turn`):

```json
{
  "session_id": "20260518_193600",
  "turn_id": "001",
  "started_at": 1747602960.42,
  "finished_at": 1747602964.18,
  "duration_s": 3.76,
  "wake_phrase": "hey gema",
  "wake_confidence": 0.91,
  "user_wav": "001.user.wav",
  "user_samples": 64000,
  "tts_wav": "001.tts.wav",
  "tts_samples": 38400,
  "finish_reason": "tts_finished",
  "whisper_transcription": "pon música",
  "whisper_raw_text": "pon música",
  "stt_reject_reason": null,
  "manual_correction": "",
  "extra": { ... }
}
```

Hoy ningún script consume eso. El bench solo lee
`duration_s + whisper_transcription` (en
`measure_voice_e2e_p95`) y nada más.

Cada sesión real es un evaluation dataset gratis — wake recall,
wake confidence distribution, STT reject reasons, TTS latency,
manual_correction una vez que el operador anote. Hace falta el
**reader**.

---

## OBJETIVO

Un commit chico. Crear `scripts/session_report.py` que:

1. Lee `~/.gemma4/recordings/<session>/manifest.jsonl`.
2. Produce un reporte humano (stdout + opcional MD) y un JSON
   estructurado.
3. Expone métricas que el bench puede consumir directamente
   (sin re-parseo).

**No es trivial**: hay que decidir qué métricas SON útiles
versus qué métricas son ruido. La guía es: si una métrica
discrimina turnos malos de buenos, sirve. Si no, no.

---

## REGLAS GENERALES

1. PortandoLoMejor. Un commit chico, prefijo `feat(ops):`.
2. **NO toques** `recorder.py`, `controller.py`, `stt.py`,
   `bench.py`. Pure observability — solo lectura.
3. **NO inventes campos** que el manifest no emite hoy.
   Si necesitás un campo nuevo, eso es Sprint T.1, no T.
4. Auto-install OK para deps free (pero ninguna debería hacer
   falta — stdlib + numpy + json son suficientes).
5. NO `git add -A`.
6. `scripts/session_report.py` debe ser ejecutable independiente
   (`python scripts/session_report.py <session_id_or_path>`).

---

## FIX T — Session report tool

### T.1 — Detección de sesión

El tool acepta:

- `python scripts/session_report.py 20260518_193600`
  → lee `~/.gemma4/recordings/20260518_193600/manifest.jsonl`
- `python scripts/session_report.py /full/path/to/manifest.jsonl`
  → lee directamente esa ruta
- `python scripts/session_report.py`
  → lee la sesión más reciente en
  `~/.gemma4/recordings/` (ordenado por mtime del manifest).
  Si no hay ninguna, exit con mensaje claro.

CLI básico:

```bash
python scripts/session_report.py [SESSION_OR_PATH] [--json OUT.json] [--md OUT.md] [--quiet]
```

`--quiet` suprime stdout pero sigue escribiendo --json/--md si
están presentes.

### T.2 — Métricas por turno

Para cada turno, calcular:

| Métrica | Origen | Tipo |
|---|---|---|
| `turn_id` | manifest | str |
| `duration_s` | manifest | float |
| `wake_phrase` | manifest | str |
| `wake_confidence` | manifest | float |
| `tts_samples` | manifest | int |
| `tts_duration_s` | `tts_samples / SAMPLE_RATE` | float |
| `whisper_transcription` | manifest | str | None |
| `whisper_raw_text` | manifest | str | None |
| `was_rejected` | `stt_reject_reason is not None` | bool |
| `stt_reject_reason` | manifest | str | None |
| `had_tts_reply` | `tts_samples > 0` | bool |
| `manual_correction` | manifest | str (puede estar vacío) |

### T.3 — Agregados por sesión

```python
@dataclass
class SessionReport:
    session_id: str
    manifest_path: Path
    turn_count: int
    turns: list[TurnRecord]

    # Wake metrics
    wake_phrases_seen: dict[str, int]          # histogram
    wake_confidence_p50: float
    wake_confidence_p95: float
    wake_low_confidence_count: int             # < 0.85

    # STT health
    transcribed_count: int                     # whisper_transcription non-empty
    rejected_count: int                        # stt_reject_reason set
    reject_reasons: dict[str, int]             # histogram
    silent_count: int                          # whisper_raw_text empty AND no reject reason

    # TTS metrics
    replied_count: int                         # tts_samples > 0
    tts_duration_p50: float
    tts_duration_p95: float

    # E2E latency (the bench-compatible signal)
    e2e_durations_s: list[float]
    e2e_p50: float
    e2e_p95: float
    e2e_max: float
```

Reglas de fmean/percentile sobre arrays vacíos:

- Si una lista de mediciones está vacía, el agregado correspondiente debe
  ser `None`. NUNCA `0.0` — eso es falso PASS si alguien lo lee.
- `e2e_p95` solo se calcula sobre turnos con
  `whisper_transcription` non-empty Y `tts_samples > 0`. Eso es
  el "happy path" — el budget de 5s está pensado para wake → TTS
  completado, no para silent rejects.

### T.4 — Salida humana

Stdout default (sin flags):

```
Session report: 20260518_193600
  Manifest: C:\Users\usuario\.gemma4\recordings\20260518_193600\manifest.jsonl
  Turns:    25

Wake
  Phrases:        hey gema (24), ey gema (1)
  Confidence:     p50=0.93  p95=0.96  low=2

STT
  Transcribed:    20 / 25 (80%)
  Rejected:       3        [reasons: ngram_repetition (2), no_speech (1)]
  Silent:         2

TTS
  Replied:        18 / 25 (72%)
  TTS duration:   p50=2.1s  p95=4.8s

E2E latency (happy path only, n=18)
  p50=3.4s  p95=5.7s  max=6.9s

bench_compat (consumable by scripts/bench.py --session-jsonl):
  n_e2e_eligible=18  voice_e2e_p95=5.7
```

Si la sesión no tiene happy-path turns (todos rejected o todos
sin TTS), imprimir explícitamente:

```
E2E latency: N/A (no happy-path turns: replied=0)
```

### T.5 — Salida JSON

Estructura idéntica al SessionReport dataclass, con
`turns: list[dict]` (los dicts son TurnRecord serializados).
Compatible con `json.dump`.

Top-level añade un bloque `bench_compat`:

```json
"bench_compat": {
  "voice_e2e_p95_eligible_turns": 18,
  "voice_e2e_p95": 5.7,
  "voice_e2e_p50": 3.4,
  "voice_e2e_max": 6.9,
  "manifest_used": "C:\\Users\\usuario\\.gemma4\\recordings\\20260518_193600\\manifest.jsonl"
}
```

Esto es lo que el bench debería poder consumir sin re-parseo
en sprints futuros. **Pero no toques bench.py en este sprint.**
Solo emití el bloque — la integración es Sprint T.1 (opcional,
después si vale la pena).

### T.6 — Integración con el bench (alternativa contemplada)

Hoy `bench.measure_voice_e2e_p95(session_jsonl)` re-parsea el
manifest. NO lo cambies en este sprint. Pero el output JSON de
T.5 emite el mismo agregado (`voice_e2e_p95`) que el bench
calcula, lo cual permite contra-validar: si el bench arroja
distinto que session_report sobre el mismo archivo, hay un bug
en uno de los dos. Eso es Sprint T.1 si se quiere agregar la
verificación.

### T.7 — Tests

`gemma4_agent/test_session_report.py`:

Mínimo de 5 tests:

1. `test_load_empty_manifest`: archivo vacío produce
   `turn_count=0` y todos los agregados `None`, no raise.
2. `test_load_single_turn`: 1 turn happy-path, valida que
   `e2e_p95 == duration_s` de ese turn y `transcribed_count == 1`.
3. `test_rejected_turns_excluded_from_e2e`: 3 turns, 2
   rejected, 1 happy. `e2e_p95` solo sobre el happy.
4. `test_reject_reason_histogram`: 4 turns con reject_reasons
   diferentes, valida `reject_reasons` dict.
5. `test_low_confidence_count`: confidence_threshold=0.85, mix
   de turns con conf 0.91/0.83/0.92/0.79, valida count=2.
6. (Opcional, recomendado) `test_path_resolution`: pasando un
   session_id resuelve a `~/.gemma4/recordings/<id>/manifest.jsonl`.
   Usar `unittest.mock.patch` sobre `Path.home` para no depender
   de filesystem real.
7. (Opcional, recomendado) `test_bench_compat_block`: el JSON
   output incluye `bench_compat` con `voice_e2e_p95` numérico
   cuando hay happy-path turns.

Todos los tests usan `tempfile.TemporaryDirectory` para escribir
manifests fake. NO toquen `~/.gemma4/recordings`.

### T.8 — Commit

`feat(ops): session report tool for manifest.jsonl analysis`

Mensaje:

```
feat(ops): session report tool for manifest.jsonl analysis

Sprint Q.0 unlocked stt_latency_p95 measurement (PASS 0.062s).
The next blocker for the production-readiness bench is
voice_e2e_p95, which is SKIPPED waiting for --session-jsonl.

But more important: every voice session recorded by
VoiceRecorder (~/.gemma4/recordings/<id>/manifest.jsonl) is an
evaluation dataset with 8+ useful fields per turn that nothing
currently reads. Wake confidence distribution, STT reject
reasons, TTS-replied count, E2E latency -- all sitting on disk.

scripts/session_report.py reads a manifest.jsonl (by session id,
full path, or "most recent") and produces:

- Stdout summary: wake/STT/TTS/E2E aggregates with sane handling
  of empty arrays (None, not 0.0).
- Optional --json output with a bench_compat block (voice_e2e_p95
  numeric for happy-path turns only) that future sprints can
  feed to bench.py --session-jsonl without re-parsing.
- Optional --md output for ops review docs.

Happy-path eligibility for E2E latency: whisper_transcription
non-empty AND tts_samples > 0. Rejected or silent turns are
NOT counted in the latency budget -- the 5s target is for
wake-to-reply, not wake-to-silent-reject.

Tests: 7 tests over tempfile fixtures. No filesystem coupling
to ~/.gemma4/recordings -- Path.home() is patched.

Read-only tool. recorder.py, controller.py, bench.py untouched.
```

---

## REPORTE FINAL

Devolveme:

1. Hash del commit.
2. Output de `python -m pytest gemma4_agent/test_session_report.py -v`.
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`
   (suite completa, no regresa).
4. Output de `python scripts/session_report.py` (sin args,
   sobre la sesión más reciente del operador; si no hay sesiones
   con manifest emitido, pegame el mensaje de error).
5. Si hay una sesión real con turns, pegame el JSON parcial
   `bench_compat` block. Si no, mostrá un manifest fake creado
   ad-hoc para demostrar que el JSON output funciona.
6. **Re-corrida del bench** apuntando al manifest de una
   sesión real (o fake):
   ```bash
   python scripts/bench.py --session-jsonl ~/.gemma4/recordings/<id>/manifest.jsonl
   ```
   Pegame el output completo y confirmá si `voice_e2e_p95`
   ahora mide (PASS/FAIL) o sigue SKIPPED con razón concreta.

## CRITERIO DE ÉXITO

- 1 commit aterrizado.
- `scripts/session_report.py` corre sin error sobre cualquier
  manifest.jsonl válido (vacío, 1 turn, N turns).
- `scripts/session_report.py --json out.json` produce JSON con
  un bloque `bench_compat`.
- ≥5 tests nuevos verdes.
- Suite completa verde (baseline Sprint 3a + E.5 admitidos).
- `bench.py --session-jsonl <path>` con un manifest real mueve
  `voice_e2e_p95` de SKIPPED a PASS o FAIL con número.

## NO HACER (anti-scope)

- NO modifiques `recorder.py` para emitir campos nuevos. Si un
  campo falta, dejá un `# TODO sprint T.1` en el tool y seguí.
- NO modifiques `bench.py`. La integración formal es T.1 si
  vale.
- NO commitees manifests reales (.jsonl bajo .gemma4) al repo.
  Está ya gitignored, pero sé explícito.
- NO inventes fixtures grandes. Si necesitás un manifest de
  prueba, generálo programáticamente en el test con
  `tempfile.TemporaryDirectory`.
- NO agregues una segunda capa de "métricas avanzadas" tipo
  speech-rate, audio energy, etc. Eso es Sprint U/W. Quedate
  con los campos que el manifest YA emite.
- NO commitees una sesión real al repo bajo
  `gemma4_agent/voice/tests/`. Si querés un fixture, generálo
  en runtime de test.

## Follow-ups documentados

1. **T.1 — Integrar el bench con session_report**: en lugar de
   re-parsear, `bench.measure_voice_e2e_p95` puede llamar
   `session_report.read_manifest(path).e2e_p95`. Reduce
   duplicación y permite que el bench arroje el mismo número
   que el report siempre. Hacelo solo si T no introduce
   complejidad — si T queda limpio, T.1 es trivial.

2. **T.2 — Operator review UI**: el JSON tiene `manual_correction`
   vacío en cada turno. Un sprint futuro podría agregar
   `scripts/session_review.py` que abre cada `.user.wav` con
   `playsound` y deja al operador escribir la corrección. Sirve
   para crear el dataset que entrena un wake mejor (R2) o
   calibrar el filter (O).

3. **T.3 — Multi-session aggregates**: cuando haya 20+ sesiones
   reales, será útil un `session_report.py --all` que agrega
   métricas across sesiones. Hoy con 0-2 sesiones reales no
   aporta — esperá a tener N.

4. **Para wake_recall**: session_report puede emitir
   `wake_phrases_seen` por sesión. Cuando R2 esté implementado,
   comparar el histograma pre/post-R2 sobre las mismas sesiones
   da una señal de regresión inmediata.
