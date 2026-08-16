# FASE 0 — Verificación de viabilidad: biasing de nombres propios en STT

> Sprint biasing — Baxy. NO se implementa código de producción en esta
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

### Ruta D — speech-to-phrase (closed-vocab FST/Kaldi) COMO SEGUNDO MOTOR

(agregada tras el pedido de RED de investigar Rhasspy3. El sucesor moderno de
Rhasspy3-STT es `OHF-Voice/speech-to-phrase`, Home Assistant Voice Chapter 9,
feb 2025.)

**Qué es:** NO transcribe libre — responde *"¿cuál de las frases que conozco
dijiste?"*. Convierte plantillas de comandos + tus entidades en un FST (Kaldi +
opengrm), entrena un LM, y reconoce SOLO frases de ese grafo. Para nombres
propios es **biasing real de verdad**: el nombre solo puede salir si está en el
grafo. Maneja palabras desconocidas con **phonetisaurus G2P** (adivina la
pronunciación de "Cyberpunk" sin diccionario) + una capa fuzzy de corrección.

**A favor (encaja con varios ejes):**
- **Biasing real** (closed-vocab) — resuelve el overfitting de raíz: el grafo se
  genera de TUS entidades (apps/áreas), dinámico y personalizado.
- **CPU-friendly** — corre <1s en Raspberry Pi 4 (HA chapter 9). Respeta STT-en-CPU.
- Español SÍ (Coqui community). Licencia **Apache-2.0** (OK).
- G2P para held-out: "Cyberpunk" se reconoce aunque nunca lo listé, si está en
  el grafo (apps instaladas).

**En contra (fricción real):**
- **Closed-vocabulary ONLY**: NO hace dictado libre. "buscá en Google qué es la
  guerra de Troya" o cualquier query abierta NO la transcribe. Gemma4 necesita
  AMBOS (comandos + dictado/preguntas libres). => speech-to-phrase NO reemplaza
  a Whisper; sería un SEGUNDO motor en paralelo (comando cerrado primero, fallback
  a Whisper para lo abierto). Es el patrón Rhasspy/OVOS.
- **Packaging**: Docker/Linux-primary, depende de Kaldi + opengrm + phonetisaurus
  (binarios nativos). NO es `pip install` limpio en Windows. Choca con la
  restricción de "release a comunidad: pip install en Win/Mac/Linux sin compilar
  nativo" ([[project... voice_pipeline_redesign clarifications]]). En Windows
  habría que dockerizar o usar WSL = fricción de setup para el user final.

**Veredicto D:** arquitectónicamente es la mejor respuesta al biasing real
CPU-friendly, y el G2P es exactamente lo que generaliza a held-out. PERO (1) es
closed-vocab => motor DUAL (no reemplaza Whisper), (2) packaging Kaldi/Docker en
Windows choca con la meta de pip-install cross-platform. Es la ruta más
ambiciosa: mayor ganancia potencial, mayor esfuerzo de integración.

---

## 1.5 REQUISITO QUE DECIDE TODO: open-vocabulary obligatorio (input de RED)

RED 2026-05-23: *"un usuario no te va a decir sí o sí los comandos que ya
existen; puede decir cualquier comando que NO está en la plantilla. ¿Qué pasa
si pasa eso? Debería poder resolverlo también."*

**Esto es el requisito decisivo y elimina cualquier solución closed-vocab PURA.**
Un asistente de propósito general DEBE manejar lo no anticipado:
- comandos fuera de plantilla ("buscá la receta de paella", "resumime este PDF"),
- nombres que el user nunca registró ("abrí el juego que bajé ayer"),
- dictado/preguntas libres ("¿qué fue la guerra de los 30 años?").

Un grafo FST (Ruta D pura) NO puede resolver nada fuera de su grafo — por diseño.
Por lo tanto:

- **Ruta D PURA queda DESCARTADA** como motor único (rompe open-vocabulary).
- **D solo sobrevive como motor DUAL**: closed-vocab para comandos conocidos
  (alta precisión en nombres) + Whisper SIEMPRE como fallback open-vocab para
  todo lo demás. El router decide o corre ambos y elige por confianza.
- El motor open-vocab (Whisper) NO desaparece en NINGÚN escenario. Es la base.
  El biasing (cualquier ruta) solo MEJORA los nombres propios SOBRE esa base,
  nunca la reemplaza.

**Implicación para la decisión:** la pregunta real no es "¿qué motor?", es
"¿qué le agrego a Whisper (que se queda) para mejorar nombres propios sin perder
el open-vocab?". Re-evaluadas bajo esa lente:

| Ruta | ¿Preserva open-vocab? | ¿Mejora nombres propios? | Costo |
|------|:---:|:---:|---|
| A NeMo/Parakeet | ✅ (es open-vocab con biasing) | ✅ real | GPU-bound, motor nuevo |
| B fork CTranslate2 | ✅ (Whisper + logit-bias) | ✅ real | fork C++ frágil |
| C inventario dinámico | ✅ (Whisper + post-corrector) | ⚠️ post-hoc, techo | bajo, ya tenemos |
| D speech-to-phrase | ✅ SOLO si es DUAL con Whisper | ✅ real en comandos | motor dual + Kaldi |
| **E Whisper + repair-LLM** | ✅ nativo | ✅ por razonamiento (open) | bajo, LLM ya corre |

A y B siguen chocando con CPU/fork. Quedan, realistas:
- **C** (Whisper + corrector dinámico) — preserva open-vocab nativamente, mejora
  nombres propios con techo, cero migración. Lo que YA tenemos, bien hecho.
- **D-dual** (Whisper open-vocab + speech-to-phrase para comandos) — mejor
  biasing en comandos, pero complejidad de motor dual + router + Kaldi packaging.

### ⛔ Ruta E — DESCARTADA por RED (2026-05-23)

RED: *"los LLM que corremos ya de por sí son muy pequeños; necesito que el
sistema de transcripción sea autosuficiente por sí mismo."*

Argumento válido y dirimente: nuestros LLM son E2B/E4B-Q4 (chicos), ya al límite
de fiabilidad para tool-calling ([[project_tool_calling_weak_models_2026_05_20]]).
Cargarles además la reparación de transcripción (a) los pone a alucinar
correcciones, (b) ACOPLA el STT a un componente débil — si el LLM falla o cambia,
el STT se degrada. **El STT debe ser autosuficiente.** => E queda descartada.
Lo que queda debe resolver el biasing DENTRO del motor de transcripción, sin
depender del LLM.

### (E original, archivada) — Whisper + reparación con el LLM residente

El LLM de Gemma4 YA está corriendo
en GPU. Úsalo como segunda pasada para reparar el transcript de Whisper:

- Whisper transcribe TODO (open-vocab, base intacta) — "abrí estimulo en estim".
- Si el corrector fuzzy NO encuentra match con alta confianza (señal de nombre
  propio mal oído), se manda UNA pasada al LLM con contexto:
  *"El usuario dio un comando de voz en Spanglish. Apps instaladas: <inventario
  dinámico>. Transcripción cruda: '<texto>'. Devolvé SOLO el comando corregido."*
- El LLM **razona**, no matchea lista: resuelve "el juego que bajé ayer",
  nombres nuevos, comandos fuera de plantilla — porque ENTIENDE, no porque el
  nombre esté en un grafo. Eso es exactamente lo que RED pide.

**Evidencia:** Wang et al. (arXiv 2502.16142): "the LLM contributes significantly
to improvements in rare word error rate (R-WER) ... without altering the
common-word baseline". El LLM repara la cola de entidades/raras sin tocar el
resto. Compass research R10 (Tier-2).

**A favor:** open-vocab nativo (Whisper se queda), generaliza por RAZONAMIENTO
(no lista) => held-out real, CPU para STT (el LLM ya está en GPU, no agrega
modelo nuevo), cero migración de motor, cero Kaldi. Resuelve el requisito de RED.

**En contra / a medir:** latencia (una llamada extra al LLM ~100-200ms, SOLO
cuando hay ambigüedad — no en cada turno); riesgo de que el LLM chico alucine
una corrección (se acota con prompt restringido + "NONE" si no está seguro);
hay que cablearlo en el hot-path de voz sin inflar el turno.

**Veredicto E:** la mejor relación generalización-real / costo / requisito-RED.
Open-vocab garantizado, generaliza por comprensión, sin migración ni Kaldi.
El costo es latencia condicional (solo en ambigüedad) — medible y acotable.

---

## 2. RECOMENDACIÓN FINAL (con datos) — restricciones convergidas

Las 4 restricciones de RED, juntas, son muy exigentes y eliminan casi todo:

1. **open-vocab** (resolver lo no anticipado) → mata D-pura y whisper.cpp-GBNF.
2. **STT autosuficiente** (sin depender del LLM chico) → mata E.
3. **STT en CPU** (la GPU es del LLM) → mata A (Parakeet GPU-bound).
4. **pip cross-platform, sin fork frágil** → mata B (fork C++) y D-dual (Kaldi/Docker).

| Ruta | open-vocab | autosuf. | CPU | pip x-plat | biasing real | held-out |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| A NeMo/Parakeet | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| B fork CTranslate2 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| C corrector autocontenido | ✅ | ✅ | ✅ | ✅ | ⚠️ post-hoc | ⚠️ techo |
| D-dual speech-to-phrase | ✅ (dual) | ✅ | ✅ | ❌ | ✅ | ✅ comandos |
| E Whisper+repair-LLM | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| whisper.cpp GBNF | ❌ | ✅ | ✅ | ✅ | ✅(closed) | ❌ |

**La única ruta que cumple las 4 restricciones a la vez es C.** Y C es
post-hoc con techo. Esa es la verdad incómoda pero honesta: **bajo el conjunto
completo de restricciones de RED, no existe una solución de biasing real
pip-installable, CPU, autosuficiente y open-vocab.** Todas las que dan biasing
real (A/B/D) rompen al menos una restricción dura.

### Qué se puede hacer DENTRO de las restricciones (Ruta C bien hecha)

C no es "biasing real en el decoding", pero es **autosuficiente, open-vocab, CPU,
pip-installable**. El trabajo de generalización honesto sobre C:

1. **Inventario DINÁMICO real**, no hardcodeado: el corrector matchea contra apps
   instaladas (`_discover_installed_apps` ya existe) + media reciente + entidades
   que el user mencionó antes. "Cyberpunk" generaliza si el user LO TIENE. El
   overfitting a corregir es "mi lista de ejemplos", no "usar lista".
2. **Quitar el hardcode del prompt/hotwords** (Steam/YouTube/Netflix enumerados)
   y reemplazar por el inventario dinámico — así no sesga solo lo que yo listé.
3. Medir held-out HONESTO: el techo de C sobre nombres que el user NUNCA tuvo es
   real y se documenta, no se esconde.

### El techo honesto y qué lo superaría (mandato #3)

C generaliza a **lo que el user tiene/mencionó**, no a "cualquier nombre del
mundo". Un nombre nuevo que Whisper-es vuelve español plausible ("estimulo") es
irrecuperable por post-corrector sin candidato. Superar ESE techo, dentro de
"autosuficiente", solo se logra con **biasing en el decoding sobre un motor
CPU+pip+open-vocab** — y ese motor HOY no existe maduro (B sería, pero es fork).
La otra salida real es **fine-tuning de Whisper-small** a Spanglish (mejora el
piso del propio motor, sigue autosuficiente y open-vocab) — costo: datos + GPU
de training (la RTX 4060 sirve para entrenar, no es runtime), riesgo de degradar
generalidad multi-usuario (se mitiga con held-out de no-regresión).

### DECISIÓN QUE NECESITO DE VOS (RED)

1. **C bien hecha** (inventario dinámico real + quitar hardcodes), medida con
   held-out honesto. Es lo único que cumple las 4 restricciones. Techo: nombres
   del entorno del user. → FASE 1 + implementación.
2. **Fine-tuning de Whisper-small** a Spanglish (autosuficiente, open-vocab, sube
   el piso del motor) — sprint de datos+training, no runtime. ¿Lo evaluamos?
3. **Relajar UNA restricción** (ej. aceptar STT en GPU → A con biasing real, o
   aceptar Docker → D-dual). ¿Cuál estarías dispuesto a ceder?
4. Otra prioridad.

NO implemento nada hasta tu OK de ruta (regla del sprint).

<!-- bloque viejo C+E archivado (E descartada por RED 2026-05-23) -->
<!-- recomendación previa C+E removida; ver sección 2 actualizada arriba -->
<!-- fin bloque archivado -->
