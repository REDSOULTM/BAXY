# SPIKE — sherpa-onnx + Parakeet-TDT-0.6B-v3 int8 (medido en la máquina, 2026-05-23)

> Eje VIABILIDAD. NO es producción. Verifica la ruta que la investigación de
> RED recomendó como GANADORA. Medido contra clips reales+sintéticos existentes.

## Lo que SÍ se confirmó (a favor)

- **pip-installable, CPU, sin compilar**: `pip install sherpa-onnx>=1.13.1` (1.13.2)
  wheel precompilado Windows/Py3.10. ✅ Carga en ~2s.
- **API de biasing real existe**: `OfflineRecognizer.from_transducer(...,
  hotwords_file, hotwords_score, decoding_method="modified_beam_search",
  bpe_vocab, modeling_unit)`. (Corrección a la investigación: NO existe
  `from_nemo_transducer`; es `from_transducer(model_type="nemo_transducer")`.)
- **LATENCIA EXCELENTE en comando corto** (audio ~1.7s, 4 threads, CPU):
  - greedy: **p50 108ms / p95 163ms**
  - modified_beam_search: **p50 120ms / p95 162ms**
  - => **~10x más rápido que whisper-small** en CPU (que daba >1s). La
    investigación se equivocó al decir "comparable"; en comandos cortos
    Parakeet es MUCHO más rápido. (RTF ~0.06-0.07.)
- **RAM**: greedy 773MB, hotwords (MBS) 1472MB. Cabe en CPU; no toca VRAM del LLM.

## Lo que NO funcionó (en contra — el motivo de migrar falla)

- **La calidad BASE de Parakeet-v3 sobre este audio Spanglish es MALA**, igual o
  peor que Whisper:
  - "abre Steam" → "A Hema Hablestan."
  - "Hey Gemma, ..." → "A Hema / Ey Jamma / Eigenma" (rompe el wake word también)
  - "Stranger Things en Netflix" → "Ponstrom Gertis in Netfix"
  - "Counter-Strike" → "Trikenstein"
- **Los hotwords NO arreglan los nombres — DESESTABILIZAN la salida.** Con
  `hotwords_score=3.0` y los nombres correctamente tokenizados a BPE
  (▁Ste+am, ▁Net+fl+ix, etc. — verificado que el vocab SÍ los representa):
  - "abre Steam" → "8 mal." (PEOR, gibberish)
  - "Daredevil...Max" → "off the dragon enough, Max" (sigue mal)
  - varios casos el biasing empeoró vs greedy.
  Coincide con Gotcha #1 de la investigación (inestabilidad MBS+TDT) PERO además
  el problema de fondo es que **el biasing no puede rescatar una transcripción
  base ya rota**: si "Steam" se oyó "Hablestan", subir el score de los tokens de
  "Steam" no alcanza para vencer la evidencia acústica mal modelada.

GOTCHA de packaging: el modelo NO trae `bpe.vocab` (la investigación lo asumía).
`text2token` requiere `bpe.model` (sentencepiece) que tampoco viene. Tuve que
construir un tokenizador BPE greedy desde tokens.txt para encodear hotwords =
fricción real, no "enchufar y listo".

## CAVEAT honesto sobre el audio del spike

Estos clips son **sintéticos (Piper)** — Parakeet-v3 fue entrenado con datos
EUROPEOS (Granary), sesgo a castellano de España; las voces Piper + acento
pueden penalizarlo injustamente. NO medí sobre voz real con anglicismos (no
existe dataset libre, held-out de RED pendiente). Es posible que sobre voz
humana real Parakeet rinda mejor. PERO: (a) Whisper-small sobre los MISMOS clips
sintéticos daba mejor base, (b) el hecho de que los hotwords DESESTABILICEN (no
solo "no ayuden") es una señal de riesgo independiente del tipo de voz.

## VEREDICTO DEL SPIKE

La ruta sherpa-onnx+Parakeet **cumple las 6 restricciones formales** (CPU, pip,
open-vocab, biasing real, autosuficiente, español) y **gana en latencia** — pero
**en la prueba medida NO mejora el reconocimiento de nombres propios; los
hotwords lo empeoran**, y la calidad base es peor que Whisper en este audio.

=> NO migrar a ciegas. El único motivo para migrar (mejor biasing de nombres) NO
se sostuvo en la medición. Antes de descartar o adoptar, falta UNA cosa decisiva
que sólo RED puede dar: **voz real con anglicismos** (su held-out). Si sobre SU
voz Parakeet+hotwords sí mejora los nombres, se reconsidera (la latencia 10x
sería un bonus enorme). Si no, Whisper-small + corrector dinámico (Ruta C) sigue
siendo el mejor compromiso.

**Recomendación:** mantener Whisper-small como motor. Reconsiderar Parakeet SOLO
con un A/B sobre voz real de RED (no sintética). El spike deja todo listo
(`scripts/spike_sherpa_parakeet.py`) para re-correr con esos clips.

---

## UPDATE 2026-05-23 — re-test con `bpe.vocab` CORRECTO + score 1.5 (post-investigación)

La investigación confirmó que mi primer test de hotwords era inválido (vocab mal
formado + score 3.0). Lo corregí:
- **`bpe.vocab` generado correcto**: el modelo no trae bpe.vocab/bpe.model, e
  instalar NeMo (torch+lightning, GBs) era caro. Lo derivé del `tokenizer.json`
  de HF (formato HF-BPE: vocab + merges) usando el **merge-rank como proxy del
  score sentencepiece**. Resultado: 8192 piezas, sherpa-onnx CARGA sin el error
  "Cannot find ID for token" — los nombres SÍ se encodean ahora.
- **score 1.5 + max_active_paths=8 + modeling_unit="bpe"** (config recomendada).

**RESULTADO: los hotwords SIGUEN sin arreglar los nombres, incluso bien
configurados.** "abre Steam"→"Hablestan" (Steam no aparece), "Netflix"→"Netfix",
"Stranger Things"→"ponjertis". Una mejora aislada: "Visual Studio Code"→"Studio
Code". En general no rescata y a veces desestabiliza.

**Causa raíz CONFIRMADA (no es config):** el encoder de Parakeet-v3 pierde la
señal acústica del anglicismo en este audio — si "Steam" se oyó "Hablestan", NO
hay hipótesis con "Steam" en el beam para que el hotword la premie. El biasing
por rescoring no puede premiar lo que no existe en las hipótesis. Coincide con
S5/caveat de la investigación: "el encoder está perdiendo la información
acústica del anglicismo; ningún rescoring lo arregla".

**PERO — sigue siendo sobre voz SINTÉTICA Piper.** La investigación es enfática
(paso S4, obligatorio): validar con voz HUMANA real antes de concluir. Parakeet-v3
es europeo (Granary); voz latina real + micro-corte natural en el anglicismo
podría rendir mucho mejor. **Mi medición no descarta Parakeet — descarta
Parakeet+hotwords-sobre-Piper.** El experimento decisivo es voz real de RED.

**Lo que queda listo y verificado para cuando RED grabe:**
- `bpe.vocab` correcto en el dir del modelo.
- `scripts/spike_sherpa_parakeet.py` para re-medir.
- La ruta SEGURA que NO depende de esto: `rule_fsts` post-proceso sobre
  greedy_search (no toca el decoder, mantiene 110ms, no puede empeorar) — para
  corregir el set cerrado de errores observados ("Hablestan"→"Steam"). Es defensa
  determinista mientras se decide el motor.

---

## UPDATE 2 (2026-05-23) — A/B SOBRE VOZ REAL DE RED (Grabación 2, wake-anchored)

Por fin medido sobre voz HUMANA real (no Piper). 6 turnos, anglicismos:
Chrome (k0,k4), GTA V (k2), Benson Boone (k5). Whisper+corrector vs Parakeet
greedy vs Parakeet+hotwords(score1.5,bpe.vocab correcto):

| turno | Whisper+corr | Parakeet greedy | Parakeet +hw |
|---|---|---|---|
| k0 "abre Chrome" (1s) | ❌ ALUCINÓ outro YouTube | ✅ "Chrome" | ✅ "Chrome" |
| k2 "GTA V" | ✅ GTA V | ✅ GTA V | ✅ GTA V |
| k4 "open Chrome" | ✅ open Chrome | ⚠️ open chrome | ✅ Open Chrome |
| k5 "Benson Boone" | ✅ Benson Boone | ❌ Benson Moon | ❌ Benson Moon |

**HALLAZGOS (sobre voz real, lo que importa):**
1. **En voz real Parakeet SÍ compite** — la investigación tenía razón: el TTS
   Piper lo penalizaba injustamente. En sintético era un desastre; en real da
   "Chrome" limpio. NO descartar Parakeet fue lo correcto.
2. **k0 es demoledor para Whisper:** "abre Chrome" (1s) → Whisper **alucinó un
   outro de YouTube** ("nos vemos en el próximo video, adiós") — el fallo crónico
   de Whisper en clips cortos. **Parakeet dio "Chrome" limpio.** Punto fuerte
   real de Parakeet: NO alucina en clips cortos.
3. **Los hotwords aportan POCO sobre voz real también:** k0/k2/k5 idénticos
   con/sin hotwords; solo k4 mejoró "open"→"Open". En k5 "Boone"→"Moon" el
   hotword no rescató (encoder oyó "Moon", no hay "Boone" en el beam). Confirma:
   el biasing no arregla lo que el encoder no captó.
4. **Whisper+corrector ganó "Benson Boone"** (su corrector fonético Double-
   Metaphone lo arregló; Parakeet no tiene ese post-proceso).

**CONCLUSIÓN HONESTA (medida en voz real):** ni Whisper ni Parakeet domina solo
— ganan casos distintos. Parakeet es más robusto en clips cortos (no alucina) y
clava "Chrome"; Whisper+corrector clava "Benson Boone". Los hotwords de Parakeet
aportan marginalmente. El n=6 es chico para un veredicto estadístico — falta el
held-out de RED (~20-30 comandos) para IC Wilson. Pero la señal cualitativa es
clara: **Parakeet vale la pena como motor, y su mayor ventaja NO es el biasing
(que aporta poco) sino que NO alucina en clips cortos** — justo el talón de
Aquiles de Whisper-small que veníamos peleando.

**Próximo paso decisivo:** grabar ~25 comandos held-out (apps/series que NO
estén en inventario) para medir Entity-Recall con IC sobre voz real, y decidir:
Parakeet-solo, Whisper-solo, o dual (Parakeet primario + corrector fonético
encima para los "Boone"→"Moon").
