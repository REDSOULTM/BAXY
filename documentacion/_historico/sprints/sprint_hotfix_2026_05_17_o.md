# HOTFIX 2026-05-17 (O) — STT filter calibration (no model upgrade)

> Sprint S baseline mostró `stt_wer_mean=0.521` (target <0.20).
> Whisper-small es el modelo final del proyecto — **NO subir a
> medium / large-v3 / large-v3-turbo**. El target real es
> latencia tier-Alexa (<300ms), no el 1.2s del bench.
>
> El único camino para mover stt_wer_mean es **calibrar los
> filtros existentes** del `_quality_check` y/o ajustar decoding
> params (beam_size, temperature, suppress_tokens). Sin tocar
> el modelo.

---

## Contexto

`gemma4_agent/voice/stt.py::_quality_check` tiene 7 gates
post-transcripción que rechazan turnos:

| # | Gate | Threshold actual | Línea |
|---|---|---|---|
| 1 | empty_or_too_short | `len(text) < 2` | 674 |
| 2 | too_many_words_for_duration | `<0.7s & >4w` or `<1.5s & >8w` | 679 |
| 3 | low_logprob (segment) | `avg_logprob < -1.0` | 686 |
| 4 | no_speech_prob (segment) | `> 0.6` | 689 |
| 5 | compression_ratio (segment) | `> 2.4` | 692 |
| 6 | BoH_match | textual phrase list | 696 |
| 7 | ngram_repetition | pathological pattern | 700 |
| 8 | text_compression_ratio | `> 2.4 & len>30` | 708 |

Sprint S bench corrió contra
`gemma4_agent/voice/tests/testaudio_groundtruth_aligned.json`
(Sprint N output): 6 turns con WER individual
`[1.0, 0.364, 0.111, 0.8, 0.667, 0.185]`, mean 0.521.

**Diagnóstico previo** (Sprint P investigation): los 2 turns con
WER 1.0 y 0.8 son **small_underproduced** — Whisper-small emite
texto muy corto vs Whisper-large que emite la frase completa.
NO son hallucinations. Son under-production en clips cortos.

Eso es importante: **los filtros no son el bug**. El bug es
que el modelo no está produciendo. Calibrar filtros más estrictos
NO va a bajar el WER de los under-produced turns (ya están
"pasando" el quality check con texto corto pero correcto).

---

## OBJETIVO

Un commit chico, alto rigor estadístico. **Antes de tocar
thresholds, MEDIR cuál filtro contribuye más al WER**. Si los
filtros no son el bottleneck, decirlo honesto y mover decoding
params (beam_size en clips cortos, suppress_tokens, prefix
biasing).

El criterio de éxito NO es "bajar WER" ciegamente. Es
**identificar y aplicar la palanca correcta con evidencia
medible**. Si la palanca correcta es "no hay ganancia
disponible sin más audio", documentarlo como tal y SKIP el
threshold con razón concreta.

---

## REGLAS GENERALES

1. PortandoLoMejor. Un commit chico, prefijo `feat(stt):` o
   `chore(stt):` según resultado.
2. **NO toques el modelo Whisper**. `WhisperModel("small", ...)`
   se queda. NO bajes a tiny, NO subas a medium. Si te tienta,
   parar y leer la memory feedback-whisper-no-upgrade.
3. **NO inventes thresholds nuevos**. Calibrá los 8 existentes
   y/o tocá decoding params. No agregues un 9no filtro.
4. **NO toques** `controller.py`, `recorder.py`, `bench.py`,
   prompts. Solo `stt.py` (gates + decoding kwargs) y tests.
5. **6 turns NO alcanzan** para calibrar 8 thresholds. Si vas a
   tocar un threshold, exigite ≥3 turns que se muevan con el
   cambio Y ≥0 turns que empeoren. Si solo 1 turn se mueve, es
   ruido — no calibres sobre él.
6. NO `git add -A`.

---

## FIX O — Diagnóstico-primero, calibración-segunda

### O.1 — Generar el reporte por-filtro

Crear `scripts/stt_filter_audit.py` que:

1. Lee `gemma4_agent/voice/tests/testaudio_groundtruth_aligned.json`.
2. Para cada turno, carga `gemma4_agent/voice/tests/<turn>.user.wav`
   (si existe).
3. Corre `StreamingSTT._transcribe_buffer` directamente sobre cada
   WAV y captura:
   - `text` (post-filter)
   - `reason` (gate que rechazó, o "ok")
   - `raw_text` (lo que Whisper realmente produjo)
   - `avg_logprob`, `no_speech_prob`, `compression_ratio` por
     segmento (los emite Whisper en cada `Segment`).
4. Compara contra el `large_text` ground truth (jiwer.wer).
5. Tabula:

| turn_id | duration | large_text | small_raw_text | reason | wer | avg_logprob | no_speech | comp_ratio |
|---|---|---|---|---|---|---|---|---|

6. Calcula contadores:
   - turnos que pasaron el filtro (reason=='ok')
   - turnos rechazados por cada gate
   - WER mean **post-filter** (lo que el bench mide hoy)
   - WER mean **pre-filter** (si forzáramos a aceptar todo)
   - delta entre los dos

Esto es **el dato crítico**: si pre-filter WER == post-filter WER,
los filtros no son el cuello de botella (no están rechazando nada
relevante). Si pre-filter es MEJOR que post-filter, hay un gate
sobre-conservador rechazando turnos buenos. Si post-filter es
MEJOR, los gates están haciendo su trabajo y la palanca está en
decoding.

CLI:
```bash
python scripts/stt_filter_audit.py
```

Salida: tabla markdown a stdout + opcionalmente
`--json reports/stt_filter_audit_<ts>.json`.

### O.2 — Decisión de calibración (post-O.1)

**Lee el output de O.1 antes de seguir.** Hay 4 caminos:

**Camino A — Filtros son el bottleneck** (post-filter WER >>
pre-filter WER):
- Identificar el gate que rechazó más turnos buenos.
- Relajar SU threshold en pequeña cantidad. Ej: si
  `no_speech_prob > 0.6` rechazó 2 turnos buenos, subir a 0.7.
- Re-correr O.1. Si WER mejora y no empeora ningún turno
  previamente bueno, commit.
- Si empeora algún turno previamente bueno (false positives
  ahora pasan), revertir.

**Camino B — Filtros están OK, decoding es el bottleneck**
(pre-filter WER ≈ post-filter WER, ambos altos):
- Tocar `_get_transcribe_kwargs`:
  - Subir `beam_size` en clips cortos (hoy es 1 para
    duration<3s; probar 3 o 5).
  - Considerar `temperature=(0.0, 0.2)` para clips cortos
    también (hoy es solo 0.0 → si Whisper colapsa, no recupera).
- Re-correr O.1. Mide WER pre/post nuevamente. Si baja, commit.
- ATENCIÓN: subir beam_size en clips cortos eleva la latencia.
  Re-correr `scripts/bench.py --threshold stt_latency_p95`
  y confirmar que sigue PASS con el target tier-Alexa (<300ms).
  Si supera 300ms, REVERTIR el cambio aunque WER haya bajado.

**Camino C — Bottleneck es prefix biasing / initial_prompt**:
- Si el O.1 reporta que `small_raw_text` es muy diferente de
  `large_text` en palabras específicas (e.g. nombres de
  apps, "Spotify" vs "Spotyfay"), eso es señal de que el
  initial_prompt no está sesgando lo suficiente.
- Esto requiere audio operator-side adicional para validar
  (no se puede calibrar prompt sobre 6 turns de un solo
  hablante). **SKIP a Camino D** y documentar.

**Camino D — No hay palanca disponible** (n=6 turnos, ninguna
intervención mueve WER significativamente):
- Esto es resultado válido. NO hagas un commit que toque
  nada para "tener algo". Commiteá SOLO el script de auditoría
  + un docs file que documente el diagnóstico:
  ```
  docs/architecture/stt_filter_calibration_2026_05_18.md
  ```
  Con:
  - WER pre/post-filter
  - Por-turn breakdown
  - Hipótesis de bottleneck (model under-production, no
    filter, no decoding)
  - Path forward: necesita N≥30 turns variados para
    re-calibrar con poder estadístico. Eso es trabajo
    operator-side (grabar testaudio_v2.wav).
- Esto NO mueve el bench (stt_wer_mean sigue FAIL 0.521).
  Pero deja la palanca correcta identificada para cuando
  haya más audio.

### O.3 — Decoding params: el espacio de búsqueda permitido

Si elegís Camino B, los kwargs editables están en
`_get_transcribe_kwargs` (alrededor de line 374 en stt.py).
Espacio de búsqueda:

| Param | Hoy | Permitido | Riesgo |
|---|---|---|---|
| `beam_size` (short) | 1 | 1,2,3,5 | latencia |
| `beam_size` (long) | 5 | 5,8 | latencia, marginal |
| `best_of` (short) | 1 | 1 | NO subir — solo aplica con T>0 |
| `temperature` (short) | (0.0,) | (0.0,), (0.0, 0.2) | divergencia |
| `compression_ratio_threshold` | 2.4 | 2.0–2.6 | inversamente proporcional |
| `condition_on_previous_text` | False | False | NO cambiar |
| `suppress_tokens` | default | default + custom | complejo |

NO toques `language`, `vad_filter`, `without_timestamps`,
`initial_prompt`. Esos están calibrados por otros sprints o
son contratos del pipeline.

### O.4 — Tests

`gemma4_agent/test_stt_filter_audit.py`:

Mínimo 4 tests. NO requieren CUDA ni audio real — usan los
mismos manifest fakes que session_report usa.

1. `test_filter_audit_runs_on_empty_input`: lista vacía de
   turnos no crashea.
2. `test_filter_audit_pre_post_consistent`: si ningún turno
   está rechazado, pre_wer == post_wer.
3. `test_filter_audit_reject_increases_wer_when_text_was_good`:
   forzar un reject sobre un turno con WER 0.1 → post_wer mean
   sube respecto a pre_wer.
4. `test_filter_audit_json_output_shape`: el JSON output tiene
   las claves `pre_wer_mean`, `post_wer_mean`,
   `gate_reject_counts`, `turns`.

Si Camino A/B y tocás un threshold en stt.py, agregar:

5. `test_threshold_change_<param>_does_not_break_<previously_passing_turn>`:
   un test que valida que el nuevo threshold no rechaza turnos
   que antes pasaban. Específico al cambio que hagas.

### O.5 — Re-correr el bench

Después de cualquier cambio (Camino A/B), correr:

```bash
python scripts/bench.py
```

Y reportar **los 5 thresholds**, no solo stt_wer_mean. Si la
calibración mejoró WER pero degradó stt_latency_p95 fuera del
target tier-Alexa (<300ms; el bench formal es <1.2s pero
nuestra restricción real es <300ms), **REVERTIR**.

### O.6 — Commit

Dependiendo del camino:

**Camino A/B** (cambio de stt.py):
```
feat(stt): <param> calibrated to <new_value>; WER <old> -> <new>

scripts/stt_filter_audit.py reveals that <gate or param> was the
contributing factor: <evidence>.

Calibrated: <param> from <old> to <new>.
WER (n=6 turns from testaudio_groundtruth_aligned.json):
  pre-change post-filter mean: 0.521
  post-change post-filter mean: <new>
  per-turn deltas: [...]

Latency check: stt_latency_p95 = <X>ms (still under tier-Alexa
<300ms target).

Tests: test_stt_filter_audit.py covers <N> cases. The change is
specific to the parameter affecting WER, not a blanket relaxation
of all gates.
```

**Camino D** (solo script + docs):
```
chore(stt): filter calibration audit -- no actionable lever
identified at n=6

scripts/stt_filter_audit.py + docs/architecture/stt_filter_calibration_2026_05_18.md
document that on the current testaudio_groundtruth_aligned.json
dataset (n=6), no filter relaxation or decoding param change
moves WER mean significantly without degrading other turns or
latency budget.

The dominant failure mode is small-model under-production on
short clips (2/6 turns have raw Whisper output much shorter than
ground truth; not filter rejection). That is NOT solvable via
filter calibration -- it requires either:
  - A larger and more variant audio set (n>=30) to validate
    decoding param changes with statistical power.
  - OR model upgrade -- explicitly OUT OF SCOPE per
    [[feedback-whisper-no-upgrade]].

Path forward: operator records testaudio_v2.wav (already
pending for wake_recall threshold). When that lands, re-run
stt_filter_audit.py against it and decide calibration with
n>=30 evidence.

bench.py stt_wer_mean remains FAIL at 0.521 -- this commit
makes the failure mode legible, not green.
```

---

## REPORTE FINAL

Devolveme:

1. Hash del commit.
2. Output completo de `python scripts/stt_filter_audit.py`
   (la tabla por-turno + los contadores).
3. Cuál de los 4 caminos elegiste y POR QUÉ (cita números
   concretos del O.1).
4. Si Camino A/B: el `git diff stt.py` mostrando el cambio
   exacto. Si Camino D: el path del nuevo docs file.
5. Output de `python -m pytest gemma4_agent/test_stt_filter_audit.py -v`.
6. Output de `python -m pytest gemma4_agent/ -q --tb=line`
   (suite completa, no regresa).
7. Re-corrida del bench:
   ```bash
   python scripts/bench.py
   ```
   Pegame los 5 thresholds. Confirmá explícitamente:
   - `stt_wer_mean`: nuevo número o sin cambio.
   - `stt_latency_p95`: NO debe haber degradado (<300ms ideal,
     <1.2s formal del bench).

## CRITERIO DE ÉXITO

- 1 commit aterrizado (en cualquiera de los 4 caminos).
- `scripts/stt_filter_audit.py` corre sin error.
- Tabla por-turno legible (pre/post WER comparable).
- ≥4 tests nuevos verdes (5 si tocaste threshold).
- Suite completa verde (baselines 3a + E.5 admitidos).
- Si stt_wer_mean mejoró: stt_latency_p95 NO degradó del nivel
  Q.0 (~60-100ms).
- Si stt_wer_mean no mejoró: hay un docs file que explica POR
  QUÉ y qué hace falta (testaudio_v2.wav con n≥30).

## NO HACER (anti-scope)

- NO cambies el modelo Whisper. Punto. Si te tienta, leé
  `memory/feedback_whisper_no_upgrade.md`.
- NO toques `controller.py`, `recorder.py`, `bench.py`,
  `wake.py`. Solo `stt.py` (y solo si Camino A/B) + tests +
  scripts/stt_filter_audit.py.
- NO agregues un gate #9 al `_quality_check`. La calibración
  es sobre los 8 existentes.
- NO calibres sobre 1 solo turn que se mueve. Es ruido.
  Requiere ≥3 turns moviéndose en la misma dirección.
- NO bajes ningún threshold solo porque "se siente mejor".
  Cada cambio necesita evidencia tabulada del O.1.
- NO commitees el output crudo de O.1 al repo (carpeta
  reports/). Está gitignored o se gitignora ahora.
- NO toques `initial_prompt` ni `FALLBACK_INITIAL_PROMPT`.
  Eso es Sprint U.
- NO toques VAD (`VAD_SILENCE_MS`, `SPEECH_RMS_THRESHOLD`).
  Eso es Sprint M.X / R2.

## Follow-ups documentados

1. **Cuando aparezca testaudio_v2.wav con n≥30 turnos**:
   re-correr `stt_filter_audit.py` y re-evaluar Camino A/B/D
   con poder estadístico real. Hoy con n=6 cualquier
   calibración es overfit.

2. **Sprint U (prompt audit)** — relacionado pero distinto:
   audita el LLM prompt (no el initial_prompt de Whisper).
   Una vez que U baje el budget LLM, el sistema tiene más
   headroom para subir beam_size en STT sin violar el budget
   total. Es la palanca complementaria a O.

3. **suppress_tokens** — si Camino C aparece como bottleneck
   en n≥30 (Whisper alucinando palabras específicas que no
   están en el initial_prompt), un sprint dedicado puede
   compilar la lista de tokens a suprimir a partir de los
   reject_reasons del manifest. Hoy es prematuro.

4. **Decoding A/B framework** — Sprint W (calibration framework
   en la lista original). Hoy con n=6 no se justifica un
   framework completo; un script standalone es suficiente.
   Cuando haya n≥30, sí.
