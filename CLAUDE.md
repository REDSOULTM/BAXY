# CLAUDE.md — Cómo trabajar en este repo

Instrucciones operativas para cualquier agente Claude que trabaje en
**Carter** (asistente de voz local Windows; antes "Gemma 4 Agent" — el
modelo sigue siendo Gemma 4). Estas reglas tienen prioridad sobre tu
comportamiento por defecto. No son aspiracionales: son verificables, y
violarlas ya costó reinicios forzados, noches de GPU y 6 sprints fallidos.
Léelas antes de tocar código.

> Nota: los **principios del producto** (medí-no-celebres, honestidad
> estructural, el LLM responde, universalidad, OSS, reproducibilidad,
> confirmá lo irreversible) viven en el **README** como filosofía del
> proyecto. Acá se repiten como reglas de trabajo porque Claude debe
> respetarlas al tocar código — pero la fuente de verdad de los valores
> del producto es el README.

---

## Los mandamientos (no negociables)

### 1. Investigá antes de decidir. Siempre.
Ninguna decisión técnica se toma "de memoria" ni por intuición. Antes de
elegir una librería, un modelo, un parámetro o una arquitectura:

- Buscá la **documentación oficial, papers, issues de GitHub, benchmarks
  reales**. Usá WebSearch/WebFetch. La fecha importa — preferí fuentes
  recientes y verificá que sigan vigentes.
- Para **modelos** (Gemma 4, Whisper, wake-word, VAD, TTS): leé sus
  cards, sus límites conocidos, sus modos de fallo, el hardware que
  asumen. No asumas que un modelo "anda" hasta ver su contrato de I/O
  (sample rate, dtype, shape, ventana, normalización).
- Para **transcripción / audio**: confirmá formato exacto (16 kHz, int16
  vs float32, tamaño de chunk, mono) leyendo el código de la librería,
  no la intuición. Un error de padding o de orden de bytes da scores ~0
  que parecen "el modelo no sirve" cuando es el harness.

**Regla dura:** si vas a afirmar "X funciona así" o "Y es mejor que Z",
o lo verificaste en una fuente esta sesión, o lo mediste vos mismo, o lo
marcás explícitamente como hipótesis sin confirmar. Nunca lo presentes
como hecho si es suposición.

### 2. Toda decisión respaldada por mejores prácticas + fuentes citadas.
Cuando propongas un approach, incluí **por qué**, con la fuente. Mejores
prácticas de programación (claridad, tests, manejo de errores, no
romper invariantes) y de arquitectura (acoplamiento, aislamiento de
dependencias, reproducibilidad). Si dos approaches compiten, mostrá la
tabla comparativa con criterios medibles, no una preferencia.

Al final de cualquier investigación, listá las fuentes como links. El
proyecto ya tiene precedente: el README cita "40+ fuentes oficiales".
Mantené ese estándar.

### 3. Medí, no celebres.
- Nunca declares éxito sin un número contra un criterio definido de
  antemano (un "gate"). Ejemplo real: el wake-word tiene gate
  `recall ≥ 0.60 ∧ fp/hr ≤ 1.0` sobre un held-out universal.
- Reportá resultados crudos aunque sean malos. "recall 0.022, FAIL" es
  más valioso que esconderlo. La honestidad sobre fallos es lo que
  permitió encontrar el bug de padding que desbloqueó Sprint 7.
- Distinguí siempre **validación sintética** de **prueba real**. Un
  0.88 sobre TTS no es un 0.88 con la voz del usuario. Decílo.

### 3.5. Probá EN VIVO con el LLM y el agente. No entregues sin eso.
**(Regla del usuario, 2026-05-27, tras un fallo repetido.)** Un cambio que
toca el comportamiento del agente NO está "listo" hasta que lo corriste
contra el LLM y el agente REALES, con el mensaje que el usuario escribiría,
y viste la cadena completa de tools + el reply. Los tests unitarios mockeados
y las pruebas de funciones aisladas NO bastan: el 4B es no-determinista y
elige caminos que tu test no anticipó (caso real: arreglaste `browser.open`
pero el 4B eligió `browser.search` y el fix no se activó; "funcionaba en los
tests" pero fallaba en vivo).

- **Vos corrés la prueba en vivo, NO se la delegás al usuario.** Nunca
  cierres con "probalo vos". Arrancá el server (`scripts/_boot_server_for_eval.py`),
  inyectá el mensaje con `agent.run_content(...)` (= la UI, seguro sin
  SendInput) y verificá el resultado real. Solo lo FÍSICO irreversible que
  no podés simular (envío real de WhatsApp con su sesión, etc.) queda para
  el usuario — y eso se dice explícito, no es la regla general.
- **Probá las VARIANTES de fraseo y los caminos de tool alternativos.** Si
  arreglás una intención, corré 3-4 fraseos distintos en vivo: el 4B puede
  rutear el mismo pedido a tools distintas (open vs search, app vs browser).
  Un fix que solo cubre el camino que tu test eligió no es un fix.
- Peligro=SOLO `gui.{type,click,keypress,...}` físico (cierra VS Code).
  `run_content`, CDP, vision/screenshot, UIA-read son seguros. Ver
  memoria `feedback_never_run_synthetic_input_lives_in_vscode_2026_05_25`.

### 4. Diagnosticá la causa raíz antes de "arreglar".
Cuando algo falla, no parchees el síntoma. Reproducí, aislá, formá una
hipótesis, probala con el experimento más chico posible, recién después
actuá. Ejemplos de esta sesión que valieron oro:
- "recall 0.02" → no era el modelo, era pad al final vs al inicio.
- "la PC se congela" → no era falta de threads bajos, era el busy-wait
  (spinning) de ONNX Runtime + falta de afinidad de CPU.

### 5. No le pases trabajo de setup al usuario.
El código garantiza sus precondiciones (paths, daemons, flags, deps).
No le digas al usuario "instalá X" o "arrancá Y con flag Z" si lo podés
hacer vos. Hay autorización para instalar dependencias gratuitas
faltantes sin volver a preguntar (VLC, ffmpeg, espeak-ng, etc.). La
guardia de compra sigue para software pago.

### 6. Confirmá antes de lo irreversible y lo que toca recursos del usuario.
- Antes de borrar/sobrescribir algo que no creaste vos, miralo primero.
- **Procesos del usuario:** este agente mató juegos y un LLM en GPU sin
  avisar. Antes de matar procesos pesados, decílo o confirmá — salvo
  que el usuario haya dado permiso explícito y vigente.
- Operaciones de horas (training, descargas de GB): estimá el tiempo y
  el costo de recursos por adelantado, y respetá si el usuario está
  usando la máquina.

---

## Restricciones de producto (vienen del usuario, son ley)

- **Todo OSS y gratis.** Sin Picovoice, sin cloud APIs de pago, sin
  excepciones. Si la única solución buena es paga, decílo y dejá que el
  usuario decida — no la implementes por defecto.
- **Uso universal.** Gemma 4 es multi-usuario, multi-idioma, multi-acento.
  NUNCA optimices sobre la voz del operador como atajo (un fine-tune
  sobre su voz mejora su recall pero degrada a todos los demás).
  Evaluá siempre contra un held-out diverso, no contra una sola voz.
- **El LLM responde. Nada de hardcodes ni respuestas enlatadas.** NO
  pongas tablas de respuestas fijas ("ok"→"Listo.", "gracias"→"De nada.")
  ni short-circuits que respondan SIN pasar por el LLM. Tampoco listas de
  keywords/apps/URLs por idioma para decidir qué hacer o qué contestar.
  Eso es frágil, monolingüe, y rompe a hablantes de otros idiomas o a
  fraseos que no anticipaste. El asistente debe SENTIRSE inteligente, no
  un árbol de if/else. Lo único determinista permitido es: (a) clasificación
  por **embeddings multilingües** con fallback seguro, (b) **guardas
  estructurales** que miden la FORMA (no el contenido) — anti-loop,
  honestidad, verificadores —, (c) resolución por **estado del SO**
  (registry, UIA, pycaw), nunca por listas hardcoded. Si dudás entre
  "respuesta enlatada rápida" y "el LLM responde", **gana el LLM**.
- **CPU para STT.** El target tiene 6 GB de VRAM consumidos por el LLM.
  Whisper corre en CPU + int8. Las cifras de GPU son solo techo de
  medición, no representativas de prod.
- **Latencia tier-Alexa.** Presupuesto de latencia por turno de voz:
  4–5 s tope; 8 s es UX catastrófica. No infles el input del LLM.
- **Hardware modesto.** Asumí laptop típico, GPU 6 GB o sin GPU dedicada.
  La RTX 4060 Ti del dev es para entrenar, no el target de runtime.

---

## Trampas concretas de este repo (ya pagadas caro — no repetir)

### ONNX Runtime congela la PC
ONNX Runtime usa todos los cores + busy-wait (spinning) por defecto. En
evals batch (miles de archivos) clava la CPU al 100% y congela Windows.
**Siempre** importá `scripts/_ort_throttle.py` ANTES de cargar modelos
en cualquier loop pesado: limita intra-op threads, desactiva spinning
(`session.intra_op.allow_spinning=0`), fija afinidad de proceso y baja
la prioridad. El runtime de voz usa `LiveKitWakeRuntime` que ya viene
con 2 threads + sin spinning.

### El wake-word LiveKit espera la frase al FINAL del window de 2 s
LiveKit paddea zeros al inicio en training. Si en eval/inferencia
paddeás un clip corto al final (audio al inicio), el score colapsa a
~0.002 y parece que el modelo no sirve. Paddeá al INICIO (audio al
final). Ver `scripts/wake_universal_eval_livekit.py::_score_audio`.

### VoxCPM segfaulta en RTX 40-series (Ada Lovelace)
Bug en SDPA durante warm-up. Para TTS de training usar `tts_backend:
piper_vits`, no voxcpm. Si hace falta voxcpm, workaround SDPA-math o
`device='cpu'`.

### Python 3.10 (runtime) vs 3.11 (training)
`livekit-wakeword` requiere 3.11; el runtime del agente es 3.10. El
training corre en el venv aislado `.venv_livekit` (3.11). Para
inferencia en runtime NO importes el paquete livekit — usá
`gemma4_agent/voice/livekit_runtime.py`, que sirve los ONNX con
onnxruntime puro (verificado idéntico al oficial al 4º decimal).

### espeak-ng en Windows escupe UTF-8, el default es cp1252
El patch en `_espeak_phonemize` está en el venv, NO en el repo. Si se
recrea `.venv_livekit`, re-aplicar: `text=False` + decode utf-8
errors=replace + tolerar None.

### YAML con paths de Windows
Comillas dobles interpretan `\h` `\t` `\u` como escapes. Usá comillas
simples para paths Windows en YAML. Corré `yaml.safe_load` después de
editar.

---

## Flujo de trabajo esperado

1. **Entendé antes de tocar.** Leé el código y los docs relevantes
   (`docs/`, `documentacion/INDEX.md`, los `sprint_prompts/`). El
   historial de git es denso y útil.
2. **Plan con gate.** Antes de un sprint, definí qué medís y cuál es el
   criterio de éxito. Escribilo.
3. **Tests.** El proyecto tiene suite de voz (`gemma4_agent/test_voice_*.py`).
   Corré los relevantes antes y después. No rompas los que pasan.
4. **Commits.** Solo cuando el usuario lo pide o el trabajo está
   verificado. Mensajes con el porqué + métricas. Cerrá con
   `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`.
   **PRIVACIDAD DEL MENSAJE (repos PÚBLICOS):** los dos remotos son públicos
   (uno es el portafolio de la organización). El mensaje de commit NO debe
   exponer la CONVERSACIÓN ni el proceso interno de trabajo: nada de "el usuario
   pidió X", "aprobado por el usuario", "el user notó", "medí en vivo y", "tras
   un fallo del usuario", referencias a sesiones de chat, a /loop, a agentes, o
   a quién decidió qué. Describí el CAMBIO y su PORQUÉ TÉCNICO en voz impersonal,
   como si lo escribiera un dev del repo sin contexto de chat: "se reentrena el
   encoder porque…", no "el usuario aprobó reentrenar". El término "usuario" SÍ
   es válido cuando se refiere al END-USER del producto (Baxy) como concepto
   técnico ("el OK del usuario ante una acción irreversible", "el idioma del
   user_text"); lo prohibido es referenciar al INTERLOCUTOR de esta conversación.
   Lo mismo aplica a comentarios de código y nombres de archivos/docs versionados.
5. **DOS REPOS ESPEJO — toda operación de git va a LOS DOS.** Este proyecto
   se publica en **dos remotos que deben quedar IDÉNTICOS**:
   - `origin` → `https://github.com/REDSOULTM/Baxy.git`
   - `asistia` → `https://github.com/202610-8016-PORTAFOLIODEPROYECTOS/asistIA.git`
     (repo de portafolio de la organización).

   **Regla dura:** cada commit/push/merge/tag se hace en AMBOS, en las MISMAS
   ramas (`main` y `Dev`), de modo que `git rev-parse main` coincida en
   `origin/main` y `asistia/main` (y lo mismo para `Dev`). Nunca pushees a uno
   solo. Si `asistia` no está como remoto en un checkout nuevo:
   `git remote add asistia https://github.com/202610-8016-PORTAFOLIODEPROYECTOS/asistIA.git`.
   Patrón estándar tras un commit en `main`:
   ```
   git push origin main && git push asistia main
   git checkout Dev && git merge main --ff-only
   git push origin Dev && git push asistia Dev
   git checkout main
   ```
   `Dev` es la rama de pruebas; cuando pasa todo, se mergea a `main`. Ambas ramas
   viven en ambos repos. Verificá la sincronía con los tres `rev-parse` antes de
   dar por cerrado un push.
6. **Memoria.** Lo no-obvio (gotchas, decisiones de producto, baselines)
   va a la memoria persistente, no se pierde entre sesiones.
7. **Procesos largos en background**, con throttle si tocan CPU/GPU, y
   estimación de tiempo comunicada al usuario.

---

## Recomendaciones para fortalecer esto aún más

Más allá de los mandamientos que pediste, sugiero adoptar:

1. **"Definición de Hecho" por tarea.** Cada cambio no está "listo" hasta
   que: tests pasan, gate medido, fuentes citadas, memoria actualizada si
   hubo un gotcha. Una checklist evita el "parece que anda".

2. **Reproducibilidad como requisito, no lujo.** Todo dataset/modelo debe
   regenerarse desde scripts versionados (ya se hace: `wake_universal_*`).
   Nunca un artefacto sin su receta. Si bajás algo de internet, dejá el
   script de descarga, no solo el archivo.

3. **Presupuesto explícito antes de gastar recursos.** Antes de un job de
   horas o GB, escribí: tiempo estimado, VRAM/CPU/disco, y qué pasa si
   falla a mitad. Esto evita el "lancé 45 h de training a ciegas".

4. **Un "experimento mínimo" antes del "experimento completo".** Smoke
   test con datos chicos para validar el pipeline ANTES de la corrida de
   producción. Ya se hizo con el config smoke — institucionalizalo.

5. **Separá hechos de hipótesis en cada reporte.** Una sección "lo que sé
   con evidencia" y otra "lo que asumo / falta confirmar". El usuario
   merece saber dónde estás parado.

6. **Trazabilidad de fuentes en el código.** Cuando un número o constante
   viene de un paper/bench, comentalo con la fuente en el código (ya se
   hace en `wake.py` con la tabla de calibración del threshold). Que el
   próximo que lo lea sepa por qué ese valor.

7. **Anti-regresión por idioma/dominio.** Para sistemas multi-usuario, un
   gate global no alcanza: ningún subgrupo fuerte debe degradarse al
   mejorar el promedio. (El wake mide recall por idioma justamente por
   esto.)
