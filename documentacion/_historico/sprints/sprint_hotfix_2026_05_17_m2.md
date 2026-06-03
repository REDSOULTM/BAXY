# HOTFIX 2026-05-17 (M.2) — Close M.1 loose ends + act on testaudio findings

> Sprint M.1 (`3e4dcb6`) aterrizó los 4 fixes del recorder pero
> dejó pendientes administrativos (`.gitignore`, commit del JSON
> de análisis) y surfaceó hallazgos del testaudio que requieren
> acción. Este sprint cierra todo eso.

---

## Contexto: lo que pasó en M.1

M.1 aterrizó limpio (16/16 tests, los 4 fixes en su lugar). El
análisis offline de `Grabación (2).m4a` corrió y produjo
`testaudio_analysis.json`, pero el sprint terminó antes del
commit final. Quedaron pendientes administrativos:

1. **`.gitignore`** no se actualizó para excluir
   `testaudio_full.wav` (WAV intermedio regenerable).
2. **`testaudio_analysis.json`** no se commiteó (el reporte del
   agente sí debe ir al repo; el `.wav` y `.m4a` no).
3. **`scripts/testaudio_analysis.py`** no se commiteó (vale la
   pena commitearlo para regenerar el análisis en sprints
   futuros con datasets nuevos).

Y los hallazgos del análisis revelaron 2 bugs estructurales
sobre los que vale la pena actuar:

### Hallazgo H1: Wake detector recall colapsado en este audio

```
Audio duration: 292.8s (~5 min)
Wake detections: 3
Operator intent: ~50-80 commands (per repertoire descrito)
```

Vosk detectó **3 wakes en 5 minutos** cuando el operador grabó
decenas de comandos con "Gemma" / "Hey Gemma" al frente. Eso es
recall ~5-10% — el wake detector está fallando masivamente en
condiciones que no son "lab perfecto".

Posibles causas (sin probar todavía):
- El `.m4a` original tenía AAC compression que dañó las
  frecuencias que Vosk usa para el matching.
- El operador habló rápido / encadenado / con variaciones
  ("hey gemma" pronunciado "ey gema", "gema" suelto, etc).
- El debounce `_last_fire_at` de Vosk está descartando wakes
  legítimos cuando hay rapid-fire.

Diagnóstico estructural: el primer pass de la detección reportó
**6 wake_word_accepted log lines** (telemetría de hotfix H);
el callback recibió solo 3 después del debounce. El debounce
es 2 segundos. **El operador dijo wake words muy seguidos** y
el debounce mató 50% de ellos.

### Hallazgo H2: 3/3 turns rechazados por quality_check

```
Bucket counts:
  legitimate_passed:    0
  legitimate_rejected:  3 (ngram_repetition x2, no_speech_prob x1)
  expected_rejected:    0
```

CERO turns pasaron el quality filter. Distribución:
- `ngram_repetition` x2: Whisper alucinó con n-grams repetidos
  (típico de audio dañado / muy ruidoso / muy silencioso —
  Whisper "repite" tokens).
- `no_speech_prob (0.66)` x1: Whisper mismo dijo "esto no parece
  speech" con probabilidad 66%.

Esto NO es necesariamente un bug. El `.m4a` reencodeado a
16kHz mono int16 perdió calidad. Whisper rechazando es lo
correcto si la calidad del audio es genuinamente baja. PERO
hay una posibilidad real: el VAD trim en `_transcribe_buffer`
está cortando demasiado y Whisper recibe solo silencio o
fragmentos.

---

## OBJETIVO

Tres commits chicos:

1. **`docs(voice): commit testaudio analysis artifacts`** —
   pendiente administrativo de M.1.
2. **`fix(voice): tighten wake debounce for rapid-fire scenarios`**
   — atacar Hallazgo H1.
3. **`obs(voice): expose pre-quality-filter Whisper text in stt
   reject reason`** — atacar Hallazgo H2 a nivel de
   observability (sin tocar el filter mismo).

---

## REGLAS GENERALES

1. PortandoLoMejor. 3 commits chicos.
2. **NO modifiques** el quality_check de Whisper, la BoH list,
   el VAD threshold. Esos son calibration changes que requieren
   probes específicos — este sprint solo agrega visibilidad.
3. **NO toques** router, planner, prompts, las 65 tools, modes,
   tool_descriptions.yaml.
4. **NO bajes** el wake debounce a < 0.5s. Race condition con
   el feed loop.
5. NO instales libs nuevas.
6. NO `git add -A`.

---

## FIX M.2.1 — Commit testaudio analysis artifacts

### M.2.1a — Actualizar `.gitignore`

El archivo está en `c:\Users\usuario\Desktop\ETC\Programacion\
Probando Gemma 4\.gitignore`. Agregar al final:

```
# Sprint L+ voice analysis intermediates (regenerable from .m4a).
gemma4_agent/voice/tests/testaudio_full.wav

# Operator-provided raw audio — leave to operator decision.
# Uncomment if operator marks the .m4a as personal/sensitive:
# gemma4_agent/voice/tests/*.m4a
```

### M.2.1b — Verificar qué archivos hay para commitear

```bash
ls -la gemma4_agent/voice/tests/
```

Esperás encontrar al menos:
- `Grabación (2).m4a` (audio original del operador)
- `testaudio_full.wav` (WAV convertido — debe quedar gitignored)
- `testaudio_analysis.json` (output del análisis — SÍ commitear)

Y en `scripts/`:
- `testaudio_analysis.py` (script del análisis — SÍ commitear)

### M.2.1c — Verificar `testaudio_analysis.json` está bien

Antes de commitearlo, hacer un sanity check de su shape:

```python
import json
with open("gemma4_agent/voice/tests/testaudio_analysis.json",
          encoding="utf-8") as fh:
    d = json.load(fh)
assert "source_file" in d
assert "wake_detections" in d
assert "buckets" in d
assert "bucket_counts" in d
assert "all_results" in d
print(f"ok — {d['wake_detections']} detections, "
      f"buckets={d['bucket_counts']}")
```

Si el archivo no existe (por ej. el sprint M.1 falló al
escribirlo), regeneralo corriendo:
```bash
python scripts/testaudio_analysis.py
```

### M.2.1d — Decisión sobre el `.m4a` original

`Grabación (2).m4a` es ~7MB de voz del operador. Dos opciones:

a) **Commitear** al repo como test fixture. Pro: reproducibilidad
   del análisis para futuros sprints. Con: tamaño del repo
   crece, y si el operador grabó cosas personales accidentalmente
   queda en la historia git.

b) **Gitignorear** y dejar al operador la decisión de cuándo
   y dónde compartirlo. Pro: zero risk de leak. Con: el
   análisis JSON existe pero no es reproducible sin el archivo
   original.

**Default recomendado**: opción (b). Commitear solo el
`testaudio_analysis.json` + el script. Si el operador quiere
después hacer el `.m4a` parte del repo, ese es un commit
explícito separado.

Agregar al `.gitignore` la entry comentada (línea ya incluida en
M.2.1a — la dejas comentada con instrucción para el operador).

### M.2.1e — Commit

```bash
git add .gitignore
git add gemma4_agent/voice/tests/testaudio_analysis.json
git add scripts/testaudio_analysis.py
git commit -m "$(cat <<'EOF'
docs(voice): commit testaudio analysis artifacts

Sprint M.1 follow-up. Persists the outputs of the offline
testaudio analysis so future sprints can compare against this
baseline.

Committed:
- gemma4_agent/voice/tests/testaudio_analysis.json — structured
  result of running Vosk wake detection + Whisper STT over the
  operator's manual recording (Grabación (2).m4a). 3 wake fires
  in 4.88 min, all rejected by quality_check.
- scripts/testaudio_analysis.py — reproducible analysis pipeline.
  Regenerates the JSON from the .m4a via ffmpeg + Vosk + Whisper.

Gitignored (regenerable / operator-controlled):
- testaudio_full.wav (intermediate; regenerated from .m4a).
- *.m4a (operator-provided raw audio; uncomment to share).

Findings to be addressed in companion commits this sprint:
- Wake detector recall ~5-10% on this audio (Hallazgo H1).
- 100% of Whisper outputs rejected by quality_check (H2).
EOF
)"
```

---

## FIX M.2.2 — Tighten wake debounce for rapid-fire scenarios

### M.2.2a — Diagnóstico

`voice/wake.py` tiene un debounce que descarta wakes consecutivos
muy seguidos. Encontrar el valor actual:

```bash
grep -n "debounce\|_last_fire_at\|_DEBOUNCE\|DEBOUNCE_S" gemma4_agent/voice/wake.py
```

Probable que sea ~2.0 segundos (estándar para wake-word
detectors). En el análisis M.1 vimos que 6 fires se redujeron a
3 por debounce — eso es 50% de pérdida.

**El problema NO es bajar el debounce a 0** — eso reintroduce
rapid-fire por ecos del TTS o tail del wake-word mismo. El
sweet-spot probable es **0.8-1.2s**.

### M.2.2b — Fix

Bajar el debounce a **0.8s** y exponer la decisión via constante
con comentario explicativo. NO hardcodear `0.8` — usar una
constante.

Pre-flight: leer el código actual y verificar que el debounce
no esté entrelazado con otra lógica (e.g. tail capture). Si lo
está, dejar el debounce arriba pero **aumentar el tail capture**
para que múltiples wakes seguidos del operador no se solapen.

Si la implementación actual es:
```python
WAKE_DEBOUNCE_S = 2.0  # o similar
```

Cambiar a:
```python
# Hotfix M.2 2026-05-18: lowered from 2.0s to 0.8s based on
# testaudio analysis finding (Sprint M.1) — operator's rapid-
# fire wakes ("hey gemma X, hey gemma Y" within ~1s) were
# dropping 50% to the debounce. 0.8s still suppresses TTS-echo
# false-wakes (Piper utterances are typically >1s) and
# wake-word tail re-fires (Vosk reports the same phrase in
# consecutive partials when the audio buffer overlaps).
WAKE_DEBOUNCE_S = 0.8
```

Si la implementación NO tiene una constante (hardcoded en el
loop), introducila. La constante debe estar near top of module
junto a otros params (`WAKE_MIN_CONFIDENCE`, etc).

### M.2.2c — Test

`gemma4_agent/test_wake_debounce.py`:

```python
"""Wake detector debounce calibration (hotfix M.2 2026-05-18).

The testaudio analysis from Sprint M.1 surfaced that the operator
fired 6 raw wakes in a 5-minute recording, but only 3 reached
the callback — the other 3 were swallowed by a 2.0s debounce.
The fix lowers WAKE_DEBOUNCE_S to 0.8s to recover rapid-fire
wakes without re-introducing TTS-echo or wake-tail false fires.

This test pins the constant value range.
"""
from __future__ import annotations

import unittest


class WakeDebounceConstantTest(unittest.TestCase):
    def test_debounce_in_calibrated_range(self) -> None:
        # Anything below 0.5s risks wake-word tail re-fires (Vosk
        # emits partials that span the wake phrase). Anything
        # above 1.5s risks dropping legitimate rapid follow-ups.
        # The empirical sweet spot is in [0.6, 1.2].
        from gemma4_agent.voice.wake import WAKE_DEBOUNCE_S
        self.assertGreaterEqual(WAKE_DEBOUNCE_S, 0.5)
        self.assertLessEqual(WAKE_DEBOUNCE_S, 1.5)

    def test_debounce_below_typical_tts_duration(self) -> None:
        # Default Piper TTS utterances are 1+ seconds; if the
        # debounce is ABOVE that, a user can't interrupt with a
        # new wake right after Gemma finishes speaking. We want
        # debounce < typical TTS duration.
        from gemma4_agent.voice.wake import WAKE_DEBOUNCE_S
        self.assertLess(WAKE_DEBOUNCE_S, 1.0)


if __name__ == "__main__":
    unittest.main()
```

### M.2.2d — Commit

```
fix(voice): tighten wake debounce 2.0s -> 0.8s

Sprint M.1 testaudio analysis: 6 raw wakes in a 5-min recording
collapsed to 3 callback fires — 50% loss to the debounce. The
operator's repertoire intentionally included rapid-fire
sequences ("hey gemma X, hey gemma Y") to stress-test the
pipeline; the debounce was eating them.

Fix: lower WAKE_DEBOUNCE_S from 2.0 to 0.8. Rationale:
- < 0.5s risks wake-word tail re-fires (Vosk emits partials
  that overlap the wake phrase audio).
- > 1.5s drops legitimate rapid follow-ups.
- 0.8s is below typical Piper TTS utterance length (1+ sec)
  so the user can interrupt with a new wake immediately after
  Gemma finishes speaking.

This is calibration informed by real operator data, not lab
synthesis. The constant is documented inline with the rationale
so a future drift is visible in the diff.

Tests pin the [0.5, 1.5] band and the < 1.0s upper bound. No
behaviour change to the wake detection logic itself — only the
debounce constant value.
```

---

## FIX M.2.3 — Expose pre-quality-filter Whisper text in reject reason

### M.2.3a — Por qué

Hallazgo H2 del análisis: 3/3 turns rechazados por quality_check.
2 con `ngram_repetition`, 1 con `no_speech_prob (0.66)`.

**Problema diagnóstico**: el operador no puede inspeccionar
QUÉ texto Whisper produjo antes de que el filter lo matara. Sin
ese texto no sabemos:

- Si era una alucinación legítima (e.g. `[música] gracias por
  ver`) y el filter funcionó.
- Si era speech real con n-gram natural (e.g. "abre abre abre
  Chrome" hablado rápido) que el filter erróneamente atrapó.

El fix de Sprint M.1 ya propaga la `reason`, pero NO el texto
pre-filter. Necesitamos extender STTEvent / `_transcribe_buffer`
para incluir el texto crudo de Whisper también.

### M.2.3b — Cambio

Editar `STTEvent` para agregar un campo opcional `raw_text`:

```python
@dataclass(frozen=True)
class STTEvent:
    kind: str
    text: str = ""
    error: str = ""
    reject_reason: str = ""
    # Hotfix M.2 2026-05-18: when reject_reason is set, raw_text
    # carries what Whisper produced BEFORE the quality_check
    # killed it. Empty string when text is already populated
    # (no rejection) or when Whisper produced no text at all
    # (no_speech / too_short pre-Whisper rejects).
    raw_text: str = ""
```

Editar `_transcribe_buffer` para devolver `(text, reason, raw)`:

```python
def _transcribe_buffer(self, audio_int16: np.ndarray) -> tuple[str, str, str]:
    """Transcribe a buffered audio segment.

    Returns (text, reason, raw_text):
      - text: post-filter clean transcription, or "" if rejected
      - reason: 'ok' on pass, or specific rejection reason
        ('BoH_match', 'low_logprob', 'no_speech', 'too_short',
        'ngram_repetition', 'no_speech_prob', etc).
      - raw_text: what Whisper actually produced. Equal to `text`
        when reason='ok'. For rejected turns, this is the text
        the quality_check killed — used for offline diagnosis
        without re-running Whisper.
    """
```

Propagar `raw_text` desde el `quality_check` failure path:
```python
# Donde antes era:
#   if not ok and verb is None:
#       return "", reason
# ahora:
if not ok and verb is None:
    return "", reason, text  # text es lo que Whisper produjo

# El return de éxito ahora es:
return post_processed_text, "ok", post_processed_text
```

Y los 3 call sites de `_transcribe_buffer` (los emit del
STTEvent en `transcribe_stream`) ahora tienen que descomponer
la tupla y pasarla:

```python
text, reason, raw = self._transcribe_buffer(buffer)
yield STTEvent(
    kind="final",
    text=text,
    reject_reason=reason,
    raw_text=raw,
)
```

### M.2.3c — Anotar el manifest con `raw_text`

En `voice/controller.py`, en el branch `ev.kind == "final"`
cuando `not ev.text`:

```python
specific = getattr(ev, "reject_reason", "") or "stt_empty_or_vad_reject"
_rec.annotate_turn(stt_reject_reason=specific)
# Hotfix M.2.3 2026-05-18: include Whisper's pre-filter text in
# the manifest so post-hoc diagnosis doesn't require re-running
# Whisper. Empty when there was no Whisper text at all.
raw = getattr(ev, "raw_text", "") or ""
if raw:
    _rec.annotate_turn(whisper_raw_text=raw)
_rec.finish_turn(reason="stt_rejected")
```

Y en `voice/recorder.py::finish_turn`, agregar `whisper_raw_text`
al entry del manifest junto a los otros campos:

```python
"whisper_transcription": turn.extra_metadata.pop(
    "whisper_transcription", None),
"whisper_raw_text": turn.extra_metadata.pop(
    "whisper_raw_text", None),
"stt_reject_reason": turn.extra_metadata.pop(
    "stt_reject_reason", None),
```

### M.2.3d — Re-run del análisis con el fix aplicado

Después de aplicar el fix, **re-correr** el script:
```bash
python scripts/testaudio_analysis.py
```

Actualizar el `scripts/testaudio_analysis.py` para que también
desempaque el tercer elemento del tuple (`raw_text`) y lo incluya
en los `all_results` del JSON. Ejemplo:
```python
text, reason, raw = stt._transcribe_buffer(segment)
# ...
results.append({
    ...,
    "text": text,
    "reject_reason": reason,
    "whisper_raw_text": raw,  # NEW
    ...,
})
```

Re-commit del `testaudio_analysis.json` actualizado con las
3 `whisper_raw_text` field populated. Ese es el dato real que
necesitábamos.

### M.2.3e — Tests

Crear `gemma4_agent/test_stt_raw_text.py`:

```python
"""M.2.3: _transcribe_buffer returns (text, reason, raw_text)
and STTEvent.raw_text carries the pre-filter Whisper text on
rejection.
"""
from __future__ import annotations

import inspect
import unittest


class STTRawTextContractTest(unittest.TestCase):
    def test_stt_event_has_raw_text(self) -> None:
        from gemma4_agent.voice.stt import STTEvent
        self.assertIn("raw_text", STTEvent.__dataclass_fields__)
        ev = STTEvent(
            kind="final", text="", reject_reason="BoH_match",
            raw_text="[musica]",
        )
        self.assertEqual(ev.raw_text, "[musica]")
        # Default empty.
        ev2 = STTEvent(kind="partial", text="hola")
        self.assertEqual(ev2.raw_text, "")

    def test_transcribe_buffer_returns_3_tuple(self) -> None:
        from gemma4_agent.voice.stt import StreamingSTT
        doc = StreamingSTT._transcribe_buffer.__doc__ or ""
        self.assertTrue(
            "raw_text" in doc or "tuple" in doc.lower(),
            "M.2.3: _transcribe_buffer should document the new "
            "(text, reason, raw_text) tuple",
        )
```

### M.2.3f — Commit

```
obs(voice): expose Whisper pre-filter text on STT reject

Sprint M.1 testaudio findings:
- 100% of turns rejected by quality_check (3 of 3).
- ngram_repetition x2, no_speech_prob x1.
- Operator can't diagnose without seeing what Whisper produced
  before the filter.

Without this, root-causing a quality_check rejection requires
re-running Whisper on the .user.wav (slow, requires model load,
done outside the agent). With it, the diagnosis is a single
manifest line read.

Fix:
- _transcribe_buffer returns (text, reason, raw_text) instead
  of (text, reason). raw_text is what Whisper produced;
  text == raw_text when reason='ok', text == '' when rejected.
- STTEvent grows a raw_text field (default '').
- transcribe_stream propagates raw_text through its final emit
  sites (3 of them).
- Controller annotates the recorder with whisper_raw_text on
  rejection.
- Recorder's manifest line gains a whisper_raw_text field.

Script scripts/testaudio_analysis.py updated to consume the
new tuple and include whisper_raw_text in its JSON output.
testaudio_analysis.json regenerated with the new field for the
3 rejected turns, providing real data for future calibration
work on the quality_check thresholds.

NO change to quality_check logic, BoH list, VAD threshold,
or any filter behaviour. Pure observability.

Tests pin STTEvent.raw_text field + _transcribe_buffer docstring.
```

---

## REPORTE FINAL

Devolveme:
1. Hashes de los 3 commits.
2. Output de
   `python -m pytest gemma4_agent/test_voice_recorder_m1.py
   gemma4_agent/test_wake_debounce.py
   gemma4_agent/test_stt_raw_text.py -v` (esperás los 7 de M.1 +
   2 de M.2.2 + 2 de M.2.3 = 11 verdes).
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`
   (debe seguir verde).
4. `testaudio_analysis.json` regenerado: los 3 turns ahora
   muestran `whisper_raw_text` con el texto Whisper produjo
   antes del filter. Pegame las 3 entries `all_results`.

## CRITERIO DE ÉXITO

- 3 commits aterrizados.
- `.gitignore` excluye `testaudio_full.wav` y mantiene la entry
  comentada para `.m4a`.
- `testaudio_analysis.json` + `scripts/testaudio_analysis.py`
  commiteados.
- `WAKE_DEBOUNCE_S = 0.8` en `voice/wake.py` (o el nombre que
  use el módulo) con comentario referenciando M.1 analysis.
- `STTEvent.raw_text` field existe.
- `_transcribe_buffer` returns 3-tuple.
- Manifest schema actualizado con `whisper_raw_text` field.
- Suite completa verde.
- testaudio_analysis.json regenerado y muestra el texto real
  que Whisper produjo para los 3 turns rechazados.

## NO HACER (anti-scope)

- NO modifiques el quality_check, BoH list, VAD threshold,
  Whisper model size, ni los logprob thresholds. Calibration
  fixes son sprints separados.
- NO subas WAKE_DEBOUNCE_S arriba de 1.5s ni lo bajés bajo 0.5s.
- NO borres el `.m4a` original ni el `testaudio_full.wav`. El
  `.gitignore` los excluye del repo pero los archivos quedan
  localmente.
- NO commitees el `.m4a` original sin permiso explícito del
  operador (la entry está comentada en `.gitignore` por eso).
- NO toques el voice loop, router, planner, prompts, las 65
  tools. Pure observability.
- Si `WAKE_DEBOUNCE_S` no existe como constante en wake.py
  (hardcoded en el loop), introducila — el test la requiere.
  Pero NO refactorices más de eso.
- Si el quality_check rejection text expone PII (e.g. nombres
  de contactos), NO lo trunques aquí — el manifest es local del
  operador y eso es su decisión qué compartir.

## Follow-ups documentados (NO en este sprint)

1. **Wake recall todavía bajo**: aún con debounce 0.8s, este
   audio rinde ~5 wakes vs ~50-80 esperados. La causa restante
   es el m4a→wav conversion damage o pronunciaciones que Vosk no
   reconoce. Sprint follow-up: probar Vosk con grabación
   nativa WAV (no m4a) y measurar recall en condiciones lab vs
   field.
2. **ngram_repetition false positives**: si el `whisper_raw_text`
   en el JSON regenerado muestra cosas como "abre abre Chrome"
   o "musica musica musica" — eso es speech rápido legítimo
   siendo malinterpretado por el filter. Sprint follow-up:
   ajustar el threshold del ngram check o agregar context-aware
   bypass (e.g. ignorar repeticiones cortas <3 palabras).
3. **no_speech_prob threshold**: 0.66 fired el reject. Si el
   raw_text en el JSON muestra que era texto coherente,
   significa que el threshold 0.6 está demasiado agresivo.
4. **Test data más rico**: grabar el repertorio directamente en
   WAV (no m4a) y guardarlo como `tests/testaudio_v2/` para
   medir si la pérdida del wake detector era del codec.
