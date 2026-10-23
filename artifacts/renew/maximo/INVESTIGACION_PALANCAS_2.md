# Segunda investigación de palancas sin reentrenar (2026-10-23)

Alcance: palancas en tiempo de inferencia para el Qwen3.5-4B ajustado (c2e1, Q4_K_M, llama-server b11609, una ranura,
q8 KV, ~53k de contexto), System One (Laya), Parakeet, Supertonic y el kernel. Mejoran acierto, honestidad o latencia
**sin reentrenar y sin tocar el prefijo** (herramientas, descripciones y sistema). Es sólo investigación: no se cambió
código. Antes se leyeron `MAXIMO.md`, `INFORME_MAXIMO.md`, `PALANCAS-pc.md`, `PALANCAS-nb.md`, `BRIEF_FT_C3.md` y los
tramos de `PROGRESO.md` sobre velocidad (l.184-186, 284-287) y de `PROGRESO-nb.md` sobre la voz (l.130-164).
«Esperada» quiere decir que la cifra no está medida en BAXY.

## Lo que ya está hecho o descartado (no se repite)

- **Medido y descartado**: MTP (p50 638 → 744 ms, `PROGRESO.md:284-286`), especulación por n-gramas (ngram-simple
  0,83 s y ngram-mod 0,82 s contra 0,81 s, `:185`), borrador Qwen3.5-0.8B (no cabe en 4 GB; en híbridos un borrador
  parcial obliga a restaurar checkpoints, PR #19493), KV f16, pensar en la duda (d2 −43), lista corta dinámica en el
  prompt (relee el prefijo), pista de candidatas tras el prefijo (P13.1), best-of-n con RM, gramática de enums
  (w5-grammar), retoques de descripciones (P2.2, P2.3), 4.1, 4.4 y 4.5.
- **Ya en el producto**: final en streaming hacia la voz (9.4, `mind.py:1419-1424`), primera frase sola con 6 pasos
  (voz D), prefijo guardado en disco (w3-speed), historial con histéresis y precalentado (1.4), lectura anticipada del
  historial mientras BAXY habla (w5-speed2), recibos honestos (8.2, 8.3, 7.1), registro de la sesión en el reloj (8.1),
  compactación de resultados viejos (1.1/1.2), hotwords del STT (w5-stt) y Laya en CPU (3.1).

Lo que queda abierto, según el informe final: la primera palabra llega ~0,9 s más tarde en turnos con herramienta
(4,3 s p50 en el e2e del holdout); las falsedades que quedan vienen de afirmar carpetas y alcances que el resultado no
dice («lo agregué en BAXY-bench», «revisé todo el archivo»); y los errores de decisión son sobre todo del modelo. En la
voz, la petición se cierra tras **0,9 s de silencio por energía** (`voice.py:36`, `END_SILENCE_S`), una espera que
ningún banco de texto ve.

## Tabla ordenada por ganancia sobre costo

| # | Palanca | Qué es | Evidencia (fuente y cifra) | Encaje en BAXY | Ganancia esperada | Costo | Riesgo | Cómo medirla |
|---|---|---|---|---|---|---|---|---|
| 1 | **Fin de turno adaptativo** (Smart Turn + silencio corto) | Al llegar a ~0,2-0,3 s de silencio, un clasificador de audio de 8 MB dice si el turno terminó. Si dice «completo» con p alta, se cierra ahí; si no, se mantiene la espera de 0,9 s (o se alarga para las pausas a media frase) | [Smart Turn v3](https://www.daily.co/blog/announcing-smart-turn-v3-with-cpu-inference-in-just-12ms/): 8 MB, 23 idiomas, 12,6-59,8 ms en CPU, español 91,97 %; [v3.1](https://www.daily.co/blog/improved-accuracy-in-smart-turn-v3-1/): español int8 90,1 %; [Pipecat](https://docs.pipecat.ai/server/utilities/smart-turn) recomienda VAD `stop_secs=0.2` con Smart Turn. En contra: [voxturn](https://huggingface.co/AustinXiao/voxturn-v1) mide en eot-bench un 38,7 % de cortes falsos en español para Smart Turn v3.2 con 300 ms de presupuesto | No toca el modelo ni el prefijo. Va en `voice.py`, que ya decodifica parciales cada 0,8 s y tiene el ONNX de Silero probado en el NB. Sólo aplica al modo con palabra de activación (pulsar para hablar ya corta al soltar) | −0,4 a −0,6 s por orden hablada, en las que el modelo vea completas | bajo-medio (ONNX en CPU, ~10-60 ms por consulta) | cortar a la persona: mitigarlo con un umbral alto para cortar pronto y la espera vieja como respaldo; RAM ~10 MB | Reproducir offline audios del dueño (los de WakewordBaxy) y los sintéticos de `medir_hotwords.py` con pausas insertadas. Medir el p50/p90 del silencio hasta el cierre y la tasa de cortes falsos (meta ≤ 2 %). Después, los 6 casos de voz del e2e |
| 2 | **Decisión anticipada** (generación preventiva) | Con el primer silencio corto se decodifica el texto final y se lanza `turn.decide` sin ejecutar nada. Si se confirma el fin del turno y el texto no cambió, la decisión ya está; si la persona sigue, se cancela y se descarta | [LiveKit Agents](https://docs.livekit.io/agents/build/audio): «preemptive generation» activa por defecto; sólo corre el LLM, la voz espera a que se confirme el turno, y la respuesta se descarta y se rehace si el contexto cambia | El kernel no ve nada hasta confirmar: los efectos y la confirmación quedan intactos. Una sola ranura: hace falta cancelar limpio (M-2). Los checkpoints del final del historial (1.4) evitan releer el prefijo tras cancelar | oculta ~0,9 s p50 de decisión (`MAXIMO.md:32`) tras la espera del fin de turno, cuando el texto no cambia | medio (cancelación, protocolo App ↔ mente) | GPU gastada si la persona sigue; carrera entre la cancelación y el turno nuevo | Traza: `preemptive_hit` (texto anticipado = final), ms ahorrados y decisiones idénticas con y sin anticipar (12/12 como en w3-speed). decision2 no cambia por construcción |
| 3 | **Verificador determinista de afirmaciones** del final contra los recibos | Antes de publicar el final se comparan sus afirmaciones con los recibos del turno: éxito dicho con `failed`, `not_run` o `unknown`; números (volumen, cuántos) distintos del recibo; carpeta o ruta nombrada distinta de `fullPath`; «revisé todo» con `bodyTruncated` o con un alcance acotado. Si no cuadra, hay una sola regeneración con una nota de hechos en el sufijo; nunca texto fijo (invariante 5) | [Tool Receipts, 2603.10060](https://arxiv.org/html/2603.10060): 91 % de detección, 4 % de falsos positivos, +12 ms (banco propio y con auto-etiquetas del LLM: sin etiquetas, el recall bajará). [AgentLTL, 2607.02599](https://arxiv.org/pdf/2607.02599): toda entidad del final debe aparecer en un resultado previo | Ataca justo lo que queda (`INFORME_MAXIMO.md:69-71`: carpetas dichas, «revisé todo»). Los recibos ya están tipados (`verification`, `fullPath`, `stateAfter`). Va en la mente o en la App, no en el prefijo | −1 a −3 falsedades claras por corrida de práctica | medio | marcas falsas: +0,7 s de regeneración y una frase peor; la morfología del español en las comparaciones | Primero **offline y sin GPU**: correrlo sobre las transcripciones guardadas de falsedades de práctica y comparar con las etiquetas a mano (precisión y recall). Después, falsedades ×6 semillas, la latencia del e2e y la tasa de regeneración |
| 4 | **Descomponer el +0,9 s tras una herramienta** antes de elegir el arreglo | Por turno con herramienta, separar `prompt_n`/`prompt_ms` de la continuación (cuánto recibo se lee), `predicted_n` hasta la primera frase y el tiempo de síntesis de esa frase. Según lo que salga: quitar del recibo los campos nulos o vacíos (sufijo, no prefijo), o cortar la primera frase en la primera cláusula larga (eso lo decide el oído del dueño) | Medido: e2e p50 3,3 → 4,3 s, «el resultado trae más hechos y la respuesta es algo más larga» (`INFORME_MAXIMO.md:24,72-73`); el modelo genera a 64 tok/s con el prefijo (`PROGRESO.md:186`) | Diagnóstico con la traza que ya existe | −0,3 a −0,6 s si el costo está en la primera frase o en el recibo | bajo | quitar campos que el modelo usa: el formato de los recibos sale en los datos de c2e1 | Traza de una e2e de práctica; luego `sound_ms` y falsedades ×3 si se tocan los recibos |
| 5 | **Precalentar al oír «Baxy»** (la 3.4 del NB, sin hacer) | Al dispararse la palabra (0,28 s p50 tras decirla) se manda a la GPU un `max_tokens:1` con el mensaje del reloj. La persona habla 1-3 s después, así que el despertar de la GPU y la relectura corta quedan ocultos | Traza del NB: `turn.decide` tras un hueco de 3-8 s tarda 388 ms con <50 tokens, frente a 148 ms sin hueco (`PALANCAS-nb.md:46`) | Va con la 2, que lo cubre en parte. No propone ni ejecuta nada | ~−0,2 s por orden hablada | bajo | casi nulo (si llega la orden durante el precalentado, espera ~100 ms) | Script de huecos con `nvidia-smi` (pstate) y `sound_ms` de órdenes habladas |
| 6 | **Laya más rápida, sin reentrenarla** | Laya mide 687 ms p50 en el producto (`BRIEF_FT_C3.md:192`) frente a ~140 ms en la fase 0 (`system_one.py:6`), y añade +0,55 s a los turnos dudosos. Hay que diagnosticar: hilos (`-t 4`) frente a núcleos físicos y la competencia con Parakeet, Supertonic y los hilos de CPU de Qwen; largo del estado (1 200 caracteres más 4 turnos); una pasada por opción o una sola | Medido en BAXY (las dos cifras de arriba). Ya está en Q8_0 (`run_renew.cmd:46`) | Sin reentrenar: hilos, afinidad y longitud de entrada. Cambiar la cuantización movería las probabilidades y obligaría a recalibrar | −0,2 a −0,4 s en turnos dudosos | bajo | otras probabilidades si cambia el texto de entrada | decision2 S1 ×3: latencia de los turnos con S1 y decisiones idénticas (la misma p de Laya con ±1e-3) |
| 7 | **Umbrales de System One recalibrados en calib**, con Laya intacta | Los umbrales 0,4 / 0,6 / 0,95 se fijaron en decision2, así que su ganancia está inflada (`MAXIMO.md:38-41`). Se fijan en el split calib con control del riesgo de acciones equivocadas | [Conformal Risk Control, 2208.02814](https://arxiv.org/abs/2208.02814) | Ya propuesto para c3 (`BRIEF_FT_C3.md:190`), pero no exige reentrenar nada | ±0 en acierto; cifras honestas; quizá −1 a −2 acciones equivocadas | bajo | más preguntas si calib es más dura que decision2 | decision2 sin los 9 ids ×3 y acciones equivocadas, con McNemar pareado (`pareado.py`) |
| 8 | **Máscara dura de nombres por lista corta**, sólo si un oráculo offline la justifica | Sin tocar el prompt: si el nombre elegido no está en la lista corta del pedido (BM25 en CPU, no el embedder de 1 320 MiB), la decisión va por el camino de la duda | [DTDR, 2512.17052](https://arxiv.org/abs/2512.17052): +23 % a +104 % frente a recuperadores estáticos (la cifra de masking duro con Qwen3-4B, 59,6 → 80,7, es la que cita `PALANCAS-pc.md:59`) | Las versiones blandas ya fallaron (P13.1, ayuda 9, 4.1). Ésta no cambia el prefijo, pero se parece a 4.1 (P028) | 0 a +2 en decision2 | bajo para el oráculo, medio para construirla | encaminar mal como en P028; el 1,4 % de los pedidos sin el oro en la lista | **Oráculo sin GPU** sobre las trazas de decision2 con `top_logprobs`: cuántos errores de nombre tienen el oro en la lista y el elegido fuera, y cuántos aciertos quedarían fuera. Sólo se construye si el neto es ≥ +3 |
| 9 | **Confianza del STT como señal de duda** | Si Parakeet da baja confianza en una palabra de contenido y Qwen duda, se pregunta («¿dijiste batería?») en vez de actuar | Evidencia débil: práctica de la industria en patentes de asistentes (la confianza del ASR anticipa respuestas fallidas, [US 9 972 318](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9972318)); sin cifra pública. Hay que comprobar si sherpa-onnx 1.13.4 da log-probs por token en el resultado offline | P028 (batería con errores de dictado → `storage.removable.list`, 6/6, conf. 0,63-0,76): Laya corrigió mal ahí | 0 a +1 en decision2; algo en el dictado del holdout | medio | más preguntas | Banco sintético de hotwords con errores, y P028 con audio |
| 10 | **Decidir de forma voraz** (temperatura 0 en `turn.decide`) | Hoy decide a 0,2 con top_k 20 (`mind.py:722,1400`). Basta `BAXY_RENEW_DECIDE_TEMPERATURE=0` | [Renze y Guven, EMNLP Findings 2024](https://arxiv.org/abs/2402.05201v3): de 0,0 a 1,0 no hay efecto significativo en la resolución de problemas | Una variable de entorno | ~0 en acierto; algo menos de varianza entre semillas | trivial | ninguno, salvo que la cola dependa del muestreo | decision2 ×3 réplicas por edición neutra y e2e ×2. Sólo se queda con Δ ≥ 0 |
| 11 | Repetir el pedido al final (P13.2, nunca probada) | El pedido de la persona dos veces en el último mensaje | [Prompt Repetition, 2512.14982](https://arxiv.org/abs/2512.14982v1): 47 de 70 a favor y 0 en contra, en modelos sin razonamiento | El efecto es mayor cuando la pregunta va antes de las opciones. En BAXY las herramientas ya van antes del pedido, y el formato es nuevo para c2e1 | 0 a +1 | trivial | formato no visto en el ajuste | decision2 ×3 |
| 12 | Detector neuronal de alucinaciones (LettuceDetect multilingüe) detrás de la 3 | Un codificador de 210M (EuroBERT, con español) marca los tramos del final que no salen del contexto | [LettuceDetect](https://cdn.jsdelivr.net/gh/KRLabsOrg/LettuceDetect@main/README.md): F1 por tramos 0,53-0,64 (v2); sin cifra de CPU | Los recibos son JSON en inglés y el final va en español: fuera de su dominio. RAM +0,2-0,6 GB sobre los 2,7 GB | incierta | medio | muchas marcas falsas con F1 de ~0,6 | Sólo si la 3 deja casos sin ver: el mismo offline de la 3 |

## Notas cortas por palanca

**1 y 2 (voz).** Es la mayor latencia que nadie ha medido: 0,9 s fijos de silencio en cada orden hablada, más ~0,2 s
de decodificación (`voice.py:36,50`). El riesgo real es cortar a la persona: con 300 ms de presupuesto, Smart Turn
corta en falso un 38,7 % de las veces en español, según un competidor y en eot-bench. Por eso la propuesta no baja el
silencio a ciegas. Smart Turn sólo **adelanta** el cierre cuando está muy seguro, y la espera actual queda como
respaldo. La 2 aprovecha esa espera: el modelo decide mientras se confirma el turno. Nada se ejecuta ni suena antes de
la confirmación, así que la seguridad del kernel no cambia. Las dos se miden fuera de los bancos de texto: hace falta
un banco de fin de turno (latencia y cortes) con audio real del dueño. La licencia de Smart Turn hay que comprobarla
antes de integrarla (el blog dice «fully open source», pero no la nombra).

**3 (honestidad).** Los recibos honestos ya cambiaron lo que el modelo **lee**. Esto comprueba lo que **dice**. En
BAXY no hay auto-etiquetas: se compara con reglas sobre campos tipados (estado, números, `fullPath`, truncado, alcance),
así que el recall será menor que el 91 % del paper. A cambio, un desajuste sólo dispara una regeneración que lee el
hecho, nunca un texto fijo. Se empieza con las clases de falsedad que quedan (carpeta dicha, «todo el archivo», éxito
sobre un fallo) y se mide offline antes de tocar el producto.

**4 (diagnóstico).** El +0,9 s es real, pero su causa no está separada: puede ser el prefill del recibo, la longitud de
la primera frase o la síntesis. Arreglarlo sin diagnóstico arriesga la honestidad ganada (los recibos largos son los
que la dan).

**6 (Laya).** Del 140 ms de la fase 0 al 687 ms del producto hay ×5 sin explicar. Lo más probable es la competencia por
la CPU (Parakeet y Supertonic también corren en CPU) o una entrada más larga. Es barato de averiguar.

**8 (máscara).** Sólo vale si el oráculo lo dice. Las tres variantes blandas o parecidas ya perdieron puntos. Esta no
mueve el prefijo, pero desvía la decisión hacia Laya como hizo la 4.1.

## Descartadas en esta investigación

| Palanca | Por qué no |
|---|---|
| Autoconsistencia o DeepConf (filtrar trazas por confianza) | Pensado para trazas de razonamiento con decenas o cientos de muestras ([DeepConf, ICLR 2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/98257285340854262185500e59bc0f28-Abstract-Conference.html)). Pensar costó −43 en d2, cada muestra extra son ~0,7 s, y Laya ya compara los rivales del 4B |
| Que el propio 4B verifique su llamada (sí/no) | Formato nunca visto por el ajuste; el verificador ya es Laya |
| Herramientas en lenguaje natural (NLT) | +18,4 puntos en su banco ([2510.14453](https://arxiv.org/html/2510.14453v1)), pero cambia el formato de llamada que c2e1 aprendió: sólo con reentreno |
| Mandar los pedidos dudosos a un modelo grande en la nube | Rompe el invariante 6 |
| Borrador de 0,8B, MTP, n-gramas, KV f16 | Ya medidos y descartados (arriba) |
| Gramática de IDs observados (windowId, appId) | La pista `window_id_spent` y el kernel ya lo cubren; necesitaría un fork del parser qwen3-coder |
| Actualizar llama.cpp por los checkpoints de los híbridos | Hay un informe de 2026 ([V2EX](https://www.v2ex.com/t/1219800)) de checkpoints que no se reutilizan en modelos híbridos y obligan a releer todo, sin PR confirmado. En BAXY basta vigilar «erasing old context checkpoint» y las relecturas completas en `llama-server.log` (ya pedido en `llm_server.py:79-80`); sólo se actualiza si el log lo muestra |

## Orden propuesto

1. Sin GPU y en paralelo: el oráculo de la 8, el offline de la 3, el diagnóstico de la 4 y el de la 6.
2. Banco de fin de turno con audio del dueño, luego la 1 y después la 2 (con la 5 dentro).
3. La 3 en el producto, si el offline da precisión ≥ 0,9.
4. La 7 y la 10 juntas en una tanda de decision2 ×3 pareada.
5. La 9, la 11 y la 12 sólo si queda tiempo y lo anterior no las cubre.

## Fuentes

- Smart Turn v3: https://www.daily.co/blog/announcing-smart-turn-v3-with-cpu-inference-in-just-12ms/
- Smart Turn v3.1: https://www.daily.co/blog/improved-accuracy-in-smart-turn-v3-1/
- Pipecat Smart Turn (VAD `stop_secs=0.2`): https://docs.pipecat.ai/server/utilities/smart-turn
- voxturn (cortes falsos de Smart Turn v3.2 en eot-bench): https://huggingface.co/AustinXiao/voxturn-v1
- LiveKit, generación preventiva: https://docs.livekit.io/agents/build/audio
- Tool Receipts (NabaOS): https://arxiv.org/html/2603.10060
- AgentLTL: https://arxiv.org/pdf/2607.02599
- LettuceDetect: https://cdn.jsdelivr.net/gh/KRLabsOrg/LettuceDetect@main/README.md
- DTDR: https://arxiv.org/abs/2512.17052
- Conformal Risk Control: https://arxiv.org/abs/2208.02814
- Temperatura y resolución de problemas: https://arxiv.org/abs/2402.05201v3
- Prompt Repetition: https://arxiv.org/abs/2512.14982v1
- DeepConf: https://proceedings.iclr.cc/paper_files/paper/2026/hash/98257285340854262185500e59bc0f28-Abstract-Conference.html
- Natural Language Tools: https://arxiv.org/html/2510.14453v1
- Checkpoints de híbridos en llama.cpp (foro): https://www.v2ex.com/t/1219800
- Confianza del ASR (patente): https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9972318
