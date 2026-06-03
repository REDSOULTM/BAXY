# HOTFIX 2026-05-17 (M) — BoH false positive: 'pon musica' rejected

> Sprint chico de hotfix. Bug surface 2026-05-18 12:08 — operador
> dijo "Hey Gemma, pon música" siete veces seguidas; las siete
> fueron rechazadas silenciosamente. Diagnóstico completo
> ejecutado por Claude usando los WAVs grabados por Sprint L
> (que funcionó bien — eso es lo que permitió encontrar este
> bug otherwise invisible).
>
> Causa raíz: la BoH (Bag of Hallucinations) list de `voice/stt.py`
> incluye `"musica"` como standalone phrase para filtrar las
> alucinaciones que Whisper genera ante silencio (`[musica]`,
> `(musica)`). Pero el guard atrapa también transcripciones
> legítimas como `"Pon musica"` o `"Pon musica. Gemma."` porque
> contienen el substring `"musica"` y son cortas.

---

## Contexto: el diagnóstico

Del manifest del Sprint L (`~/.gemma4/recordings/20260518_120744/
manifest.jsonl`), 7 turns consecutivos con
`stt_reject_reason: "stt_empty_or_vad_reject"` y `whisper_
transcription: null`. Re-corriendo esos WAV manualmente contra
el Whisper actual (`StreamingSTT._transcribe_buffer`):

```
turn_11151750.user.wav (14s):
  transcribe pass1: dur=12.55s mode=long ok=False
  reason=BoH_match text='Pon musica. Gemma.' avg_lp=-0.74
  quality_check rejected (BoH_match): text='Pon musica. Gemma.'

turn_11176750.user.wav (13.4s):
  transcribe pass1: dur=11.50s mode=long ok=False
  reason=BoH_match text='Pon musica.' avg_lp=-0.70
  quality_check rejected (BoH_match): text='Pon musica.'

turn_11201390.user.wav ('abre esteam', PASSED):
  transcribe pass1: dur=1.19s mode=short ok=True
  reason=ok text='Abre Steam.' avg_lp=-0.52
```

Whisper transcribió bien. El BoH check (línea 639) rechazó. El
operador no tuvo forma de saberlo — el reply nunca llegó.

## Por qué la BoH catch atrapa 'pon musica'

`voice/stt.py:111-133`:
```python
SPANISH_HALLUCINATION_PHRASES = (
    "suscribete",
    ...
    "[musica]",
    "[aplausos]",
    "musica",            # <-- standalone, no brackets
)
```

`voice/stt.py:143-158`:
```python
def looks_like_hallucination(text: str) -> bool:
    t = _strip_diacritics(text).strip().rstrip(".!?,;: ")
    for phrase in SPANISH_HALLUCINATION_PHRASES:
        p = _strip_diacritics(phrase)
        if p in t and len(t) < len(p) + 20:
            return True
    return False
```

Aplicado a `"Pon musica."`:
- `t = "pon musica"` (10 chars post-strip).
- Iteramos: cuando `phrase = "musica"`, `p = "musica"` (6 chars).
- `"musica" in "pon musica"` → True.
- `len("pon musica") = 10 < 6 + 20 = 26` → True.
- → BoH match → quality_check returns `(False, "BoH_match")` →
  transcribe() returns `""`.

Mismo bug afecta cualquier transcripción corta que mencione
"música": "pone musica", "quiero escuchar musica", "musica de
fondo", "para la musica", "stop musica", etc. Lista de tools
que la usan ESPECÍFICAMENTE para queries reales: media (Spotify,
YouTube Music, Netflix soundtracks), audio (volume control durante
playback).

Razón histórica de tener `"musica"` standalone: Whisper a veces
genera tokens como `[musica]` o `(musica)` cuando el audio es
silencio o ruido sutil — son sound-effect tags de subtítulos del
training set. Pero la entry naked `"musica"` es over-broad.

---

## OBJETIVO

Un commit chico. **Quitar la entry standalone `"musica"` de la
BoH list y mantener solo las formas con corchetes/paréntesis**
que son las alucinaciones reales que Whisper genera.

---

## REGLAS GENERALES

1. PortandoLoMejor. Un commit chico, prefijo `fix(voice):`.
2. **NO toques** la lógica del BoH check (`looks_like_
   hallucination`), solo la list de phrases.
3. **NO toques** otras phrases de la list (`suscribete`,
   `gracias por ver`, etc.) — esas atrapan alucinaciones reales
   sin atrapar speech legítimo.
4. **NO toques** otros components: router, VAD, Whisper model,
   recorder, prompts.
5. NO instales libs nuevas.
6. NO `git add -A`.

---

## FIX M — Update BoH list

### M.1 — Editar `gemma4_agent/voice/stt.py:111-133`

Buscar:
```python
SPANISH_HALLUCINATION_PHRASES = (
    "suscribete",
    "suscribete al canal",
    "no olvides darle like",
    "dale like",
    "gracias por ver",
    "gracias por ver el video",
    "hasta la proxima",
    "hasta el proximo video",
    "subtitulos realizados por la comunidad de amara.org",
    "subtitulos por la comunidad de amara",
    "subtitulos creados por la comunidad",
    "amara.org",
    "subtitulado por",
    "aegisub",
    "hola a todos",
    "bienvenidos a este canal",
    "bienvenidos al canal",
    "que tal amigos",
    "[musica]",
    "[aplausos]",
    "musica",
)
```

Reemplazar la última línea (la entry standalone `"musica"`) por
formas con brackets/paréntesis que son las alucinaciones reales
de Whisper:

```python
SPANISH_HALLUCINATION_PHRASES = (
    "suscribete",
    "suscribete al canal",
    "no olvides darle like",
    "dale like",
    "gracias por ver",
    "gracias por ver el video",
    "hasta la proxima",
    "hasta el proximo video",
    "subtitulos realizados por la comunidad de amara.org",
    "subtitulos por la comunidad de amara",
    "subtitulos creados por la comunidad",
    "amara.org",
    "subtitulado por",
    "aegisub",
    "hola a todos",
    "bienvenidos a este canal",
    "bienvenidos al canal",
    "que tal amigos",
    # Sound-effect tags Whisper sometimes hallucinates in silence.
    # Keep the bracketed/parenthesized forms; the standalone word
    # "musica" was removed 2026-05-18 because it falsely rejected
    # legitimate user requests like "pon musica" (7 silent rejects
    # observed in real session 12:08 — diagnosed via Sprint L
    # recordings). See manifest at
    # ~/.gemma4/recordings/20260518_120744/manifest.jsonl.
    "[musica]",
    "(musica)",
    "[aplausos]",
    "(aplausos)",
    "[risas]",
    "(risas)",
)
```

Cambios concretos:
- **Eliminado**: `"musica"` (línea 132 actual, standalone, sin
  brackets).
- **Agregado**: `"(musica)"`, `"(aplausos)"`, `"[risas]"`,
  `"(risas)"` — formas equivalentes con paréntesis y la entry
  común para risas. Mismas alucinaciones, capturadas
  explícitamente como tags.
- **Sin cambios**: el resto de la list y la función
  `looks_like_hallucination`.

### M.2 — Test

Crear `gemma4_agent/test_stt_boh_filter.py`:

```python
"""Regression test for the Bag of Hallucinations filter.

Hotfix M 2026-05-18: the standalone 'musica' entry in
SPANISH_HALLUCINATION_PHRASES was rejecting legitimate user
queries like 'pon musica' / 'quiero escuchar musica'. Diagnosis
via Sprint L recordings: 7 silent rejects in a single 12:08
session, all real speech, all containing 'musica'. The fix
removed the standalone entry and kept only the bracketed/
parenthesized forms ([musica], (musica)) which are Whisper's
actual silence hallucinations.

This test pins the contract: legitimate 'musica' queries pass,
true sound-effect tags get rejected.
"""
from __future__ import annotations

import unittest

from gemma4_agent.voice.stt import (
    SPANISH_HALLUCINATION_PHRASES,
    looks_like_hallucination,
)


class BoHFilterTest(unittest.TestCase):
    # --- Negative cases: must NOT be flagged as hallucination ---

    def test_pon_musica_is_not_hallucination(self) -> None:
        # The motivating bug for hotfix M.
        self.assertFalse(looks_like_hallucination("Pon musica"))
        self.assertFalse(looks_like_hallucination("Pon musica."))
        self.assertFalse(looks_like_hallucination("Pon musica. Gemma."))

    def test_pon_musica_with_diacritics_is_not_hallucination(self) -> None:
        self.assertFalse(looks_like_hallucination("Pon música"))
        self.assertFalse(looks_like_hallucination("Pon música."))

    def test_other_legitimate_musica_queries(self) -> None:
        # Real user phrasings that mention 'musica'.
        for q in [
            "quiero musica",
            "pone musica relajante",
            "escucha musica",
            "stop musica",
            "musica clasica por favor",
            "baja la musica",
            "no quiero musica ahora",
        ]:
            with self.subTest(q=q):
                self.assertFalse(
                    looks_like_hallucination(q),
                    f"{q!r} falsely flagged as hallucination",
                )

    # --- Positive cases: still must catch real hallucinations ---

    def test_bracketed_musica_tag_is_hallucination(self) -> None:
        # Whisper's actual silence hallucination.
        self.assertTrue(looks_like_hallucination("[musica]"))
        self.assertTrue(looks_like_hallucination("(musica)"))
        self.assertTrue(looks_like_hallucination("[Musica]"))

    def test_bracketed_aplausos_tag_is_hallucination(self) -> None:
        self.assertTrue(looks_like_hallucination("[aplausos]"))
        self.assertTrue(looks_like_hallucination("(aplausos)"))

    def test_subscribe_phrases_still_caught(self) -> None:
        # Regression check: the other BoH entries still work.
        self.assertTrue(looks_like_hallucination("Suscribete al canal"))
        self.assertTrue(looks_like_hallucination("gracias por ver el video"))
        self.assertTrue(looks_like_hallucination("subtitulos por la comunidad de amara"))

    def test_phrases_list_no_longer_contains_standalone_musica(self) -> None:
        # Pin: ensure the standalone entry doesn't sneak back in.
        self.assertNotIn("musica", SPANISH_HALLUCINATION_PHRASES)
        # Bracketed forms remain.
        self.assertIn("[musica]", SPANISH_HALLUCINATION_PHRASES)
        self.assertIn("(musica)", SPANISH_HALLUCINATION_PHRASES)


if __name__ == "__main__":
    unittest.main()
```

### M.3 — Smoke real con los WAVs grabados por Sprint L

Después de aplicar el fix, re-correr los WAV rechazados:

```python
import os, wave, numpy as np
from gemma4_agent.voice.stt import StreamingSTT

t = StreamingSTT()
t.load()

base = os.path.expanduser('~/.gemma4/recordings/20260518_120744')
for name in [
    'turn_11151750.user.wav',
    'turn_11165234.user.wav',
    'turn_11176750.user.wav',
    'turn_11189640.user.wav',
    'turn_11216562.user.wav',
    'turn_11227796.user.wav',
    'turn_11240703.user.wav',
]:
    p = os.path.join(base, name)
    with wave.open(p, 'rb') as wf:
        raw = wf.readframes(wf.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16)
    text = t._transcribe_buffer(audio)
    status = "PASS" if text else "REJECT"
    print(f"{status:7s} {name}: {text!r}")
```

**Expectativa post-fix**: los 7 WAVs ahora transcriben a "Pon
musica" o variantes. Cero rechazos silentes.

### M.4 — Commit

`fix(voice): drop standalone 'musica' from BoH list (false positive)`

Mensaje:

```
fix(voice): drop standalone 'musica' from BoH list (false positive)

Bug surfaced 2026-05-18 12:08: operator said "Hey Gemma, pon
música" seven times in a row. Every one was silently rejected.
Other commands ("abre Steam", "tienes Batman") worked fine.

Diagnosis (made possible by Sprint L recordings):

  ~/.gemma4/recordings/20260518_120744/manifest.jsonl
    7 turns with stt_reject_reason='stt_empty_or_vad_reject'
    and whisper_transcription=null, durations 11-20 seconds.

  Replaying the WAVs through StreamingSTT manually:
    turn_11151750: dur=12.55s text='Pon musica. Gemma.'
                   ok=False reason=BoH_match (rejected)
    turn_11176750: dur=11.50s text='Pon musica.'
                   ok=False reason=BoH_match (rejected)

Whisper transcribed correctly. The Bag-of-Hallucinations check
in _quality_check rejected because SPANISH_HALLUCINATION_PHRASES
contained "musica" as a STANDALONE entry. The check fires when
phrase is a substring of the transcribed text AND text length is
< phrase + 20 chars:
  "musica" in "pon musica" -> True
  len("pon musica") = 10 < 6 + 20 = 26 -> True
  -> match -> reject

Historical rationale: Whisper sometimes hallucinates "[musica]"
or "(musica)" sound-effect tags when handed silence (it's in the
subtitle training set). The standalone "musica" entry was meant
to catch those, but is far too broad — it rejects every short
user query about music.

Fix:
- Remove "musica" standalone from SPANISH_HALLUCINATION_PHRASES.
- Explicitly add the bracketed/parenthesized forms that are the
  actual Whisper hallucinations: "[musica]", "(musica)",
  "[aplausos]", "(aplausos)", "[risas]", "(risas)".
- No change to looks_like_hallucination logic or any other BoH
  phrase.

Tests:
- Negative cases: "Pon musica", "Pon música", "quiero musica",
  "escucha musica", etc. — all pass (not hallucination).
- Positive cases: "[musica]", "(musica)", "[aplausos]" — still
  flagged as hallucination.
- Other BoH entries (suscribete, gracias por ver, amara.org)
  still caught.
- Pin: standalone "musica" must never re-appear in the list.

Smoke verification: replaying the 7 rejected WAVs from the
2026-05-18 session through the fixed code now transcribes them
all to "Pon musica" or variants. Zero silent rejects.

This bug was completely invisible before Sprint L. The recorder
preserved the actual audio + the rejected-state metadata, which
made the diagnosis trivial. Validates the design choice of
recording every wake -> tts-end window for future debugging,
not just Whisper training.
```

---

## REPORTE FINAL

Devolveme:
1. Hash del commit.
2. Output de `python -m pytest gemma4_agent/test_stt_boh_filter.py -v`.
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`
   (debe seguir ~1056 + 7 nuevos = ~1063, mismo failed Sprint 3a).
4. Smoke real (M.3) con los 7 WAVs del operador. Output esperado:
   ```
   PASS    turn_11151750.user.wav: 'Pon musica. Gemma.'
   PASS    turn_11165234.user.wav: 'Pon musica.'
   ...
   ```

## CRITERIO DE ÉXITO

- 1 commit aterrizado.
- ≥7 tests nuevos verdes en test_stt_boh_filter.py.
- Suite completa verde (modulo Sprint 3a + E.5 xfail).
- Los 7 WAVs rechazados ahora transcriben sin BoH_match.
- "[musica]" / "(musica)" / "[aplausos]" siguen siendo rechazados
  como hallucination (regresión protegida).

## NO HACER (anti-scope)

- NO toques `looks_like_hallucination` lógica. Solo la list.
- NO quites otras phrases (`suscribete`, `gracias por ver`, etc.).
  Esas siguen atrapando alucinaciones reales sin falsos
  positivos conocidos.
- NO bajes el threshold de length (`len(t) < len(p) + 20`). El
  20 está bien para las phrases más largas; el problema era la
  phrase standalone corta, no el threshold.
- NO agregues una "allow list" de verbos (`pon`, `escucha`, etc.)
  delante de "musica" — sería matching de idioma del user.
  El fix simple (quitar la entry) resuelve el problema sin
  introducir lógica per-idioma.
- NO toques recorder, router, planner, prompts, modes.
- NO migres SPANISH_HALLUCINATION_PHRASES a config / YAML. La
  list hardcoded en stt.py con comentario explicando es lo
  correcto.

## Follow-ups documentados (NO en este sprint)

1. Si después de un mes de uso aparece OTRO false positive de BoH
   (e.g. "gracias" standalone si el operador usa "gracias" como
   greeting frecuente), atacarlo con el mismo patrón: identificar
   la phrase exacta y especializarla.
2. Re-procesar los 7 WAVs históricos del 2026-05-18 con el fix
   aplicado y agregarlos al training set como ejemplos
   gold-standard de "pon musica" — usefuldata para Whisper
   fine-tuning post-Sprint L.
