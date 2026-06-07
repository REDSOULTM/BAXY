# SPIKE — sherpa-onnx + Parakeet-TDT-0.6B-v3 int8 (medido en la máquina, 2026-05-23)

> **Nota de nomenclatura:** la wake word del producto es hoy **"Baxy"**. Donde
> este documento dice "Hey Gemma" / "Gemma", es el texto medido de los
> experimentos ASR de esa época; se preserva tal cual porque son mediciones de
> cómo el reconocedor oye esa palabra puntual, no el nombre del producto.

> Eje VIABILIDAD. NO es producción. Verifica la ruta que la investigación de
> RED recomendó como GANADORA. Medido contra clips reales+sintéticos existentes.
>
> **Nota de nomenclatura:** la wake word del producto es hoy **"Baxy"**. El
> ejemplo "Hey Gemma → ..." de abajo es una **medición de error de ASR sobre la
> wake word de entonces ("Gemma")** y se conserva como hallazgo. El **modelo**
> sigue siendo Gemma 4 (de Google); no confundir la wake word con el LLM.

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

---

## UPDATE 3 (2026-05-23) — investigación "meter el nombre en el beam" + verificación en código

Investigación profunda (compass_artifact_wf-6e2efce2). Verifiqué SUS afirmaciones
de código en MI máquina (no en docs):

**VERIFICADO en código instalado:**
1. `blank_penalty` existe en greedy NeMo. PERO medido sobre k5 "Benson Boone":
   bp=0.0→2.0 → **"Benson Moon" PERSISTE en todos los valores**. Confirma: la
   fusión "Boone→Moon" es del ENCODER, no del decoder. blank_penalty arregla
   sílabas SALTADAS (doing→∅), NO confusiones del encoder. En NUESTRO caso no
   ayuda (lo medí, no lo asumí).
2. El result de sherpa SÍ expone `ys_log_probs`, `tokens`, `timestamps`, `words`
   — gating por confianza es viable.
3. `lm`/`lm_scale` y `lodr_fst` → la investigación dice que en el path NeMo son
   no-op (PR #3077 "Removed unused LM rescoring code"). No los uso.
4. `modified_beam_search` en v1.13.2 → bug ~33% fallo (issue #3267, fix #3589 NO
   está en 1.13.2). NO usar MBS en prod hasta upgrade. Quedarse en greedy.

**EL HALLAZGO QUE CIERRA EL PLAN:** mi corrector fonético ACTUAL (Double
Metaphone + fuzz) YA rescata "benson moon"→"benson boone" (txt=87, meta=86, ambos
> threshold) y "espotifai"→"spotify" (meta=89). El problema del A/B NO fue el
corrector — fue que **el corrector corre sobre la salida de WHISPER, no de
PARAKEET**. Si adopto Parakeet como motor y CABLEO mi corrector existente sobre
SU salida, combino lo mejor medido: Parakeet no alucina (gana "Chrome" en clips
cortos) + corrector rescata fusiones (gana "Boone"). La investigación valida
exactamente esto (su capa #1: "Parakeet motor + corrector post-hoc, capa
OBLIGATORIA"). Mejora propuesta por la investigación: sumar Metáfono Español
(Mosquera 2012, amsqr/Spanish-Metaphone) al corrector para cuando el hispano
pronuncia el anglicismo "a la española" — Double Metaphone solo está sesgado a
fonética inglesa.

**PLAN VERIFICADO (pendiente OK de RED para implementar en prod):**
- Motor: Parakeet-v3 greedy (no alucina, ~110ms, CPU). Mantener Whisper como
  fallback configurable.
- Encima: el corrector fonético existente (cableado sobre la salida de Parakeet)
  + Metáfono Español, gateado por `ys_log_probs` en el slot post-verbo.
- NO usar MBS/hotwords/LM/LODR (medidos como no-aplicables o inestables en 1.13.2).
- Medir con held-out de RED (IC Wilson) antes de hacerlo default.

---

## UPDATE 4 (2026-05-23) — Etapa 0 de la investigación, VERIFICADA en máquina

La investigación (plan_sherpa_parakeet_cpu_optimizacion.md) priorizó rescate
post-hoc sobre fp32 (sin evidencia de que fp32 arregle fusiones). Verifiqué sus
3 puntos de Etapa 0 en NUESTRA máquina:

1. **MBS bug #3267 NO persiste en 1.13.2** (la investigación lo INFERÍA; ahora
   CONFIRMADO empíricamente). MBS sobre los 6 turnos reales = texto correcto, sin
   "Yeah"/vacíos. Más: k4 MBS dio "Open Chrome" limpio vs greedy "E gema open
   chrome". => PR #3589 está en 1.13.2. **HOTWORDS REABIERTOS como vía válida.**
2. **feature_dim NO es bug**: default del wrapper es 80, pero sherpa-onnx ignora
   ese valor para modelos NeMo y usa el correcto (128) del propio ONNX. Salida
   idéntica con fd=80 y fd=128. Conjetura de la investigación descartada (bien
   verificarla, no aplica).
3. **Threads**: 16 físicos / 24 lógicos -> num_threads = min(4, físicos) = 4
   (coincide con el óptimo medido p50 150ms en UPDATE previo).

**PLAN DE IMPLEMENTACIÓN (pendiente OK de RED):**
Etapa 1 (apuesta principal): rescate post-hoc determinista — extraer slot por
verbo-comando/timestamps, corrector fonético ES+EN (Double Metaphone jellyfish +
Spanish Metaphone Mosquera + RapidFuzz) contra inventario dinámico. Cablear sobre
la salida de Parakeet (mi corrector actual YA rescata "benson moon"->"boone").
Etapa 2: como MBS anda en 1.13.2, sumar hotwords (modeling_unit=bpe, score 1.5)
como PREVENCIÓN, no rescate.
fp32: DIFERIDO (sin evidencia de fix; +1.8GB RAM, ~2x latencia).

---

## UPDATE 5 (2026-05-23, noche) — Etapa 2 MEDIDA: MBS-hotwords RECHAZADO por evidencia

Verificado que `modified_beam_search` + hotwords es ESTABLE en sherpa 1.13.2
(PR #3589 efectivo: no alucina, no desestabiliza). En casos sueltos rescata
(crumb→chrom, Thunder Birth→Thunderbird). PERO sobre el set COMPLETO de RED:

| Config | Entity-Recall | p50 |
|---|---|---|
| greedy (crudo) | 64% [52,75] | 75 ms |
| MBS-hotwords 1.5 (crudo) | 64% [52,75] | 98 ms |
| **greedy + corrector** | **81% [70,89]** | **73 ms** |
| MBS-hotwords + corrector | 78% [67,86] | 98 ms |

CONCLUSIÓN: el corrector sobre greedy DOMINA. Los hotwords sobre-sesgan (vuelven
incorrectas salidas greedy que estaban bien), cancelando sus rescates, y suman
~25ms. **Decisión: producción = Parakeet greedy + corrector. NO hotwords.**
Coincide con la apuesta principal del plan (rescate post-hoc > trucos de decoding).

## UPDATE 6 (2026-05-23) — Etapa 3 (slot re-transcription) PROBADA y NO IMPLEMENTADA

Probé hotwords agresivos (score 2.5/3.5/5.0) sobre los 6 residuales severos:
- score 2.5: rescata 2/6 (gimp, reddit); score 3.5: 1/6; score 5.0: 0/6 (basura
  "Red","Edg"). chrome→chrom, edge→echo, zoom→su NUNCA recuperan.
CONCLUSIÓN: las fusiones residuales son límite ACÚSTICO/encoder (Parakeet no
capturó esos fonemas del audio), no rescatables por decoding. Etapa 3 daría ≤2
rescates inestables a cambio de latencia + riesgo de degradación catastrófica.
NO se implementa. El corrector @81% es el operating point correcto. Coincide con
la predicción del plan (límite estructural del encoder de 600M).
