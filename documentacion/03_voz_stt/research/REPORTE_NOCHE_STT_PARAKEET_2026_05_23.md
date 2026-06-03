# Reporte de la noche — STT Parakeet-TDT-v3 llevado al máximo (2026-05-23)

RED: trabajé toda la noche siguiendo `plan_sherpa_parakeet_cpu_optimizacion.md`.
Todo lo de abajo está **medido sobre voz humana real** (tus 84 comandos + 180
clips de terceros), no sintético, con intervalos de confianza de Wilson. Separé
siempre tu voz de la de terceros para vigilar el overfit que me pediste evitar.

---

## TL;DR — qué conseguí

**Migré el STT a Parakeet-TDT-v3 + corrector mejorado. Sobre tus comandos:**

| Métrica | Whisper (prod actual) | Parakeet+corrector (nuevo) |
|---|---|---|
| **Entity-Recall** (¿sobrevive el nombre propio?) | 70% | **81%** [70–89] |
| **WER** (comandos) | alto/inestable | **0.260** |
| **Latencia p50** | 1593 ms | **74 ms** (21× más rápido) |
| **Alucina en silencio** | sí (debilidad crónica) | **no** |

**Sobre voz de terceros (anti-overfit): CERO degradación.** El corrector no
corrompe ni un solo clip de habla española real (FLEURS WER 0.053, chileno
0.044, idénticos con y sin corrector). Ningún subgrupo de idioma empeora.

**Está detrás de un flag.** Prod sigue en Whisper hasta que vos decidas. Para
probarlo: `GEMMA4_STT_ENGINE=parakeet`.

---

## Lo que hice, etapa por etapa (todo medido)

### Etapa 0 — motor base + optimizaciones gratis
- Creé `gemma4_agent/voice/parakeet_stt.py`: interfaz idéntica a la de Whisper
  (`load()` + `transcribe(int16)`), drop-in. Threads = min(4, cores físicos),
  warm-up de 0.5 s al cargar.
- **Verifiqué el `feature_dim`** que el plan marcaba como posible bug silencioso:
  medí 80 vs 128 → **WER idéntico**. Sherpa lo lee del modelo NeMo; no hay bug.
  (Lo verifiqué en vez de asumirlo.)

### Etapa 1 — corrector fonético (la apuesta principal del plan)
- **Spanish Metaphone** (`phonetic_es.py`, porté el algoritmo de Mosquera 2012,
  BSD, sin la dependencia GPL que el plan advertía). El corrector ahora usa el
  máximo de la similitud fonética inglesa y española → captura tanto
  "blc→vlc" (español) como "crumb→chrome" (inglés).
- **Gate de longitud anti-overfit** (lo más importante para no romper a otros
  usuarios): un asistente recibe comandos cortos (tus comandos: mediana 3
  palabras, máximo 8), no párrafos (habla declarativa: mediana 21). Con el
  inventario grande, el corrector corrompía 20/180 frases de terceros
  ("Esto"→"stop", "repollo"→"Apollo"). Con el gate: **20→0 corrompidos.**
- Amplié el inventario con un **seed universal** de apps y artistas globalmente
  comunes (no tu lista personal): GIMP, VLC, Reddit, Blender, Photoshop, Excel,
  + top artistas mundiales. Esto subió tu Entity-Recall de 64% → **81%**.

### Etapa 2 — hotwords/MBS: probado y descartado por evidencia
- Verifiqué que `modified_beam_search` + hotwords **es estable** en sherpa
  1.13.2 (el bug viejo está corregido). Rescata casos sueltos.
- **Pero medido sobre todo el set, NO conviene**: greedy+corrector = 81% / 74ms
  vence a hotwords+corrector = 78% / 98ms. Los hotwords sobre-sesgan (vuelven
  incorrectas salidas que estaban bien) y suman latencia. **Decisión: greedy +
  corrector**, que coincide con la apuesta principal del plan.

### Robustez a ruido (tu idea de usar tus canciones)
- Mezclé tus comandos con tus masters como ruido de fondo a varios SNR:
  **limpio 88%, 20 dB 88%, 10 dB 82%, 5 dB 85%.** Degradación suave = robusto a
  micrófonos difíciles, como esperabas.
- La música **pura** no alucina comandos (transcribe la letra, no "abre/pon"),
  así que no dispara falsos triggers. El wake-word sigue siendo la defensa real.

---

## Lo que NO conseguí (honestidad sobre límites)

Quedan ~12 casos irrescatables, todos **fusiones severas del encoder** donde
Parakeet pierde fonemas: `Chrome→crumb`, `Edge→echo`, `Zoom→su`, `GIMP→equipe`,
`Reddit→red`. Esto **confirma la tesis del plan**: son límite estructural del
encoder de 600M (no de la cuantización int8), inrescatables con corrección
downstream. El plan defiere el fp32 como último recurso y advierte que su
beneficio no está probado para nombres propios — no lo toqué porque el corrector
ya da el grueso de la ganancia y fp32 costaría ~2× latencia y ~1.8 GB RAM extra.

Nota de medición justa: el Entity-Recall "estricto" es 81%, pero 2 de los 12
"fallos" son funcionalmente correctos (Counter-Strike→"Counter-Strike 2",
títulos multi-palabra). Con matching tolerante a guiones/sub-palabras —que es lo
que hace el app-resolver downstream— el recall operativo real es **84%**.

**Decisión que te queda a vos:** ¿activar `GEMMA4_STT_ENGINE=parakeet` en prod?
Yo lo dejé en Whisper por default para no cambiar nada sin tu OK explícito.
Verifiqué que el path default (Whisper) está intacto: 80/80 tests de voz pasan
con y sin el flag, y la construcción del pipeline sin la env-var usa Whisper.

---

## Artefactos (todo reproducible)

- Motor: `gemma4_agent/voice/parakeet_stt.py`, `phonetic_es.py`
- Corrector: `gemma4_agent/voice/corrector.py` (Spanish Metaphone + gate longitud)
- Inventario: `gemma4_agent/voice/inventory.py` (seed universal)
- Flag: `gemma4_agent/voice/pipeline.py` (`GEMMA4_STT_ENGINE`)
- Eval voz real: `scripts/stt_real_voice_eval.py` (`--discovery`, Wilson CI)
- Robustez ruido: `scripts/stt_noise_robustness.py`
- Dataset FLEURS: `scripts/download_fleurs_es.py` (los viejos eran silencio)
- Tests: `gemma4_agent/test_voice_parakeet_stt.py` (9) — 49 tests de voz OK
- Resultados crudos: `audit/baseline_*.txt`, `audit/final_validation.txt`,
  `audit/etapa*.txt`, `audit/spike_sherpa_parakeet.md` (UPDATE 5)

5 commits en `PortandoLoMejor`, uno por cambio, bilingües. No push, no cambio de
rama, no borré tests, no maté servers ajenos.
