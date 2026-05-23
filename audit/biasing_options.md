# FASE 0 — Verificación de viabilidad: biasing de nombres propios en STT

> Sprint biasing — Gemma4 Agent. NO se implementa código de producción en esta
> fase. Se evalúan 3 rutas con spike mínimo y se recomienda UNA con datos.
> Entorno medido: faster-whisper 1.2.1, ctranslate2 4.7.1, Python 3.10, Windows,
> RTX 4060 (training) / CPU int8 (runtime prod).

---

## 0. Qué es `hotwords` HOY (verificado en el CÓDIGO instalado, no en docs)

**Conclusión: `hotwords` ≡ `initial_prompt`. Es prepend de tokens al prompt del
decoder, NO modificación de logits, NO shallow-fusion.** La sesión anterior se
había confundido; RED y la doc oficial tenían razón.

Evidencia — `faster_whisper/transcribe.py` línea 1542-1548 (versión 1.2.1
instalada):

```python
if previous_tokens or (hotwords and not prefix):
    prompt.append(tokenizer.sot_prev)
    if hotwords and not prefix:
        hotwords_tokens = tokenizer.encode(" " + hotwords.strip())
        if len(hotwords_tokens) >= self.max_length // 2:
            hotwords_tokens = hotwords_tokens[: self.max_length // 2 - 1]
        prompt.extend(hotwords_tokens)      # <-- prepend al prompt, nada más
```

`hotwords` se tokeniza y se mete en el prompt tras `sot_prev`, igual que
`initial_prompt`. No toca el beam-search ni los logits.

Evidencia adicional — `ctranslate2.models.Whisper.generate` (4.7.1) expone:
`beam_size, patience, length_penalty, repetition_penalty, no_repeat_ngram_size,
suppress_tokens, suppress_blank, sampling_*`. **NINGÚN** parámetro de biasing
contextual / logit-bias / bias_words. El shallow-fusion del PR de CTranslate2
NO está en esta versión.

**Implicación:** `hotwords` y el prompt enriquecido sufren el mismo techo de
U-WER (sesgan lo enumerado, no generalizan a held-out). No son la solución al
overfitting; son parte del problema.

---

## 1. Las 3 rutas — spike y veredicto

### Ruta A — motor con biasing nativo (NeMo / Parakeet)

**Existe biasing REAL en NeMo** (a diferencia de faster-whisper): CTC-based Word
Spotter / GPU-accelerated phrase-boosting tree, shallow-fusion en greedy y beam
"sin degradación notable de velocidad" (arXiv 2406.07096, 2508.07014 TurboBias;
docs.nvidia.com word_boosting). Esto es lo que la literatura recomienda.

**PERO choca con nuestra restricción dura — el STT de prod corre en CPU:**
- `nvidia/parakeet-tdt-0.6b-v3`: español SÍ (25 idiomas EU), licencia CC-BY-4.0
  (OK). 600M params, ~2GB RAM. **GPU-optimizado; CPU "not recommended for
  production"** (model card). Sin ONNX documentado. El biasing/word-boosting NO
  está en la model card de Parakeet-TDT v3 — vive en el framework NeMo con
  setups CTC/Transducer específicos, no es "enchufar y listo".
- Restricción del proyecto: la RTX 4060 6GB la consume el LLM en prod; el target
  es laptop modesto, STT en CPU int8 ([[feedback_stt_cpu_only]]). Parakeet en CPU
  es lento y no recomendado -> rompe el presupuesto de latencia tier-Alexa.

**Veredicto A:** biasing real, pero (1) GPU-bound vs nuestra restricción CPU,
(2) el biasing no es trivial de habilitar en Parakeet-TDT, (3) cambia el motor
entero + framework NeMo pesado. Alto esfuerzo, choca con CPU-only. NO recomendada
para prod salvo que se mueva el STT a GPU (decisión de producto del user).

### Ruta B — fork CTranslate2 con el PR de shallow-fusion

- Confirmado: `ctranslate2.models.Whisper.generate` (4.7.1 instalada) NO tiene
  ningún parámetro de biasing/logit. El PR sigue ABIERTO sin mergear (RED lo
  verificó). Usarlo = compilar un fork de CTranslate2 (C++/CMake) y mantenerlo
  des-sincronizado de master.
- Friction: build C++ en Windows + mantener fork no-mergeado + re-build en cada
  update de faster-whisper. Riesgo alto, mantenimiento eterno.

**Veredicto B:** da el biasing real sobre Whisper, pero fork frágil no-mergeado,
compilación C++ en Windows, mantenimiento perpetuo. NO recomendada (la regla del
sprint dice "sin forks frágiles sin documentar").

### Ruta C — quedarse en faster-whisper, arreglar el overfitting del corrector

**Spike de la pregunta clave: ¿se puede detectar "anglicismo mal transcrito" por
FORMA genérica, SIN lista? → NO de forma fiable.** Medido (heurística de
"españolidad": terminación, k/w, clusters ingleses, 3+ consonantes):

```
anglicismos mal transcritos:  netflis=0  disnei=1  jema=1  estimulo=1  espotify=0
palabras españolas normales:  persona=1  ventana=1  musica=1  guerra=1   esquina=1
```

Los anglicismos mal transcritos **puntúan igual que el español normal**. Razón
de fondo: cuando Whisper-es se equivoca con un nombre inglés, produce algo que
PARECE español válido ("Steam"→"estimulo" es una palabra española real). Por eso
una detección por forma NO puede distinguir "estimulo (era Steam)" de "estimulo
(palabra real)" — son el MISMO token. La desambiguación REQUIERE o contexto
(qué app/título tiene sentido) o un conjunto de candidatos contra el cual matchear.

**Conclusión teórica dura:** un mecanismo list-free, por forma, tiene techo. La
generalización real NO es "sin lista" — es **lista DINÁMICA y PERSONALIZADA**:

- El repo YA tiene `_discover_installed_apps()` (inventory.py) que aumenta el
  inventario con las apps REALMENTE instaladas del user. "Cyberpunk" generaliza
  si está instalado; "King Lear" si está en su biblioteca.
- El overfitting actual NO es "usa una lista" (eso es correcto y necesario) —
  es "usa MI lista hardcodeada de ejemplos en el prompt + un inventario estático
  que yo curé". El fix de generalización: que la lista venga del ENTORNO del user
  (apps instaladas, media reciente), no de mis hardcodes.

**Veredicto C:** viable sobre el stack actual, sin migración ni forks. El techo
de "cualquier nombre del mundo sin lista" es inalcanzable por teoría (arriba),
PERO "cualquier nombre que el USER realmente tiene" SÍ es alcanzable vía
inventario dinámico. Bajo esfuerzo, cero riesgo de migración.

---

## 2. RECOMENDACIÓN (con datos) — y PARADA para decisión del user

**Recomiendo Ruta C, con un encuadre honesto del techo.**

Por qué C y no A/B:
- **A (NeMo/Parakeet)** tiene el biasing real que la literatura recomienda, pero
  es **GPU-bound** y nuestra restricción dura es **STT en CPU** (la GPU es del
  LLM en prod). Adoptarla = o mover STT a GPU (decisión de producto tuya) o
  correr Parakeet en CPU (lento, no recomendado). Además el biasing de Parakeet-
  TDT no es enchufable trivial.
- **B (fork CTranslate2)** da biasing real sobre Whisper pero es un fork C++
  no-mergeado = mantenimiento perpetuo + build en Windows. Va contra "sin forks
  frágiles".
- **C** no migra nada, y el spike muestra que el verdadero overfitting no es
  "usar lista" sino "usar MI lista". Cambiar a **inventario dinámico**
  (apps instaladas + media reciente del user) generaliza a lo que el user
  realmente tiene, sin tocar el motor.

**El techo honesto de C (lo que NO va a resolver):** un nombre que el user NUNCA
tuvo/mencionó y que Whisper convierte en una palabra española plausible
("estimulo") es teóricamente irrecuperable sin contexto o sin que ese nombre
esté en SU entorno. Eso NO es un fallo de C — es el límite de cualquier
post-corrector. Lo único que lo superaría es biasing en el decoding (A/B) o
fine-tuning, ambos con el costo descrito.

**DECISIÓN QUE NECESITO DE VOS (RED):**
1. ¿Aceptás Ruta C (inventario dinámico, sin migración) como dirección? ó
2. ¿Querés evaluar mover el STT a la RTX 4060 en prod para habilitar Ruta A
   (biasing real, pero rompe el "STT en CPU")? ó
3. ¿Otra prioridad?

NO implemento nada hasta tu OK de ruta (regla del sprint).
