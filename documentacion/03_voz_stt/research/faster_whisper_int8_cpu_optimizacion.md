> **Nota sobre la wake word (actualización de nomenclatura):** la wake
> word del producto es hoy **"Baxy"**. Esta investigación se escribió
> cuando la palabra de activación era "Gemma", y los ejemplos de colisión
> fonética que cita ("Hey Gemma" → "Hey Kema", re-segmentación de "Gemma")
> son **hallazgos de research sobre esa palabra concreta** y se conservan
> tal cual por trazabilidad. Donde el texto solo usa la wake word como
> ejemplo genérico del patrón "wake-word + comando", leelo como **"Baxy"**.
> El **modelo** sigue siendo Gemma 4 (de Google); no confundir la wake
> word con el LLM.

Resumen ejecutivo y diagnóstico del problema
Optimización de faster-whisper small int8 CPU para asistente de voz local en español (Voice Stack)
Resumen ejecutivo y diagnóstico del problema
El comportamiento descrito ("Hey Gemma, abre Steam" → "Hey Kema! ¡Aurestín!", "abre estímulo", invenciones varias) corresponde a un patrón muy bien documentado de Whisper cuando se le entrega audio corto, con silencios al inicio/final, sin contexto previo y con vocabulario fuera de distribución (anglicismos como Steam, Spotify). Las causas confirmadas por la literatura y por issues oficiales son:

Whisper es un decoder autorregresivo entrenado con teacher forcing sobre 680 k horas de audio de internet (mayoritariamente YouTube). En ausencia de contenido reconocible, el decoder cae en priors del corpus de entrenamiento ("suscríbete", "gracias por ver", "subtítulos creados por la comunidad de Amara.org", "♪♪", etc.). Esto es lo que produce sustantivos y exclamaciones inventadas en clips cortos.
El modelo siempre razona sobre ventanas de 30 s de log-mel. Si el audio dura 1–2 s, el resto se rellena internamente con ceros. Whisper "ve" mucho silencio y el head de language modeling tiende a fabricar texto. Esto está confirmado en el paper original de OpenAI (sec. 3.8) y en openai/whisper discussion #1606, #1783, #1873.
condition_on_previous_text puede meter en loops de repetición. Está bien que lo tengas en False, pero por sí solo no resuelve invenciones puntuales.
without_timestamps=True aumenta alucinaciones según observación empírica de Sanchit Gandhi (HuggingFace, mantenedor de Whisper en transformers): forzar al modelo a emitir timestamps lo "ancla" al audio y reduce divagaciones. Este es probablemente uno de los cambios de mayor impacto que puedes hacer hoy.
beam_size=5 con audio muy corto produce más alucinaciones que beam_size=1, hallazgo cuantificado en arXiv 2501.11378 (Investigation of Whisper ASR Hallucinations Induced by Non-Speech Audio, AGH Kraków, 2025): "The lowest hallucination rate is achieved for beam size equal to 1."
El modelo small en multilingüe es relativamente débil para nombres propios técnicos en español ("Steam" → "estímulo", "Tim", "Aurestín"). Esto no es un bug; es OOV. Se mitiga con initial_prompt + hotwords + suppress_tokens y, si fuera posible, con un modelo mayor (medium o turbo).
La ausencia de un VAD/recorte previo hace que el padding de 0.3 s y, sobre todo, los snippets cortos post wake-word con cola de silencio o ruido residual, sean exactamente el caso patológico identificado en la literatura.

La conclusión es que el problema no es de configuración aislada sino multifactorial: hay que actuar simultáneamente sobre (a) parámetros de decoding, (b) prompting/biasing, (c) preprocesamiento del audio entregado al modelo y (d) filtrado posterior. Cualquier cambio individual da mejoras marginales; la combinación que se propone al final del reporte elimina la mayoría de los casos reportados.
Las fuentes principales utilizadas a lo largo del reporte son el código fuente de SYSTRAN/faster-whisper (transcribe.py, vad.py), el código de openai/whisper (transcribe.py, decoding.py), el paper original de Whisper (Radford et al., 2022), la guía oficial de prompting de OpenAI (developers.openai.com/cookbook/examples/whisper_prompting_guide), los papers académicos arXiv 2501.11378 (AGH Kraków, hallucinations on non-speech), 2505.12969 (Calm-Whisper), 2402.08021 (Careless Whisper), 2410.18363 (Contextual Biasing), 2309.09552 (Multitask Whisper + KWS) y posts técnicos verificables de Sanchit Gandhi (HuggingFace), Deepgram y la documentación de Home Assistant / Rhasspy.
1. Anti-alucinación en Whisper para audio corto (<2 s)
1. Anti-alucinación en Whisper para audio corto (<2 s)
1.1 Mecánica de la alucinación en clips cortos
El receptive field fijo de 30 s del encoder Whisper implica que cualquier audio < 30 s se completa con padding (ceros en el espectrograma log-mel). El decoder, condicionado por los tokens especiales <|sot|><|es|><|transcribe|> y, en tu caso, <|notimestamps|>, comienza a emitir tokens autorregresivamente. En ausencia de información acústica suficiente, la distribución de salida se acerca a la del language model puro del decoder, que ha visto un corpus dominado por subtítulos de YouTube en muchos idiomas. De ahí los priors típicos en español: Medium

"Suscríbete al canal." / "Gracias por ver el video." / "No olvides darle like."
"Subtítulos realizados por la comunidad de Amara.org"
"♪♪♪" o variantes con notas musicales
"Música" en mayúsculas como descripción
En francés "Sous-titres réalisés par l'Amara.org", en inglés "Thanks for watching!", "Thank you.", "I", "you", etc.

Estos priors son los responsables de transformaciones como "abre Steam" → "¡Aurestín!" o "abre estímulo" — el modelo encuentra silencio post-comando, no tiene contexto y emite la palabra española más probable foneticamente cercana.
La pregunta natural es por qué Whisper se "pierde" justamente en comandos cortos cuando un humano los entiende sin esfuerzo. La razón es triple:

El encoder procesa 30 s pero el decoder está entrenado para producir transcripciones del orden de 5–25 segundos típicamente; en 1–2 s tiene menos evidencia acústica para anclar la salida. Medium
La proporción señal/silencio en el log-mel es desfavorable: aprox. 3 % de la ventana contiene audio útil. Esto se acerca al régimen de "audio mudo" del que se sabe que dispara fabricaciones (issues #1606, #1783, #679 de openai/whisper).
La presencia del wake-word "Gemma" pegado al comando, sin una pausa natural, induce al modelo a interpretar "Gemma" como una palabra desconocida y a re-segmentarla foneticamente ("Hey Kema").

1.2 Padding de silencio: cuánto, dónde y por qué
Hay consenso experimental (Discussion #1606 de openai/whisper; el PR #1838 de OpenAI que añadió clip_timestamps precisamente para skip de silencio inicial; arXiv 2402.08021 Koenecke et al., Cornell) en que silencios largos al inicio y al final del clip son los disparadores principales de alucinaciones. El paper Careless Whisper (Koenecke et al., FAccT 2024) demostró que ajustar el umbral de decibelios para trimear silencio reduce las hallucinations en datos de AphasiaBank. Healthcare Brew
Recomendaciones operativas para tu caso:

No agregues padding largo al inicio. El pad de 0.3 s al final está bien, pero si lo aumentas a 1–2 s, multiplicarás las alucinaciones. El paper Investigation of Whisper ASR Hallucinations Induced by Non-Speech Audio (Smiałek-Wegrzyn et al., AGH 2025, Tabla IV) muestra que aumentar la duración de no-speech al inicio o final escala monotónicamente la tasa de alucinaciones.
Mejor estrategia: trimear el silencio agresivamente antes de pasarlo a Whisper, dejando ≤ 100 ms al principio y ≤ 200–300 ms al final. Si vienes de RMS-endpoint, ya tienes los índices de inicio/fin del speech: úsalos para hacer un crop tight.
No insertes silencio artificial al inicio para "completar 30 s". Whisper ya hace ese padding internamente con ceros. Insertar más silencio audible (no cero) puede activar todavía más al language head.
Si el audio es < 1.0 s, considera rechazarlo antes de invocar Whisper (probablemente sea ruido o tos). Un asistente tipo Alexa no responde a clips de 200 ms.

1.3 no_speech_threshold, log_prob_threshold, compression_ratio_threshold
Estos tres parámetros forman el temperature-fallback loop del paper original (sec. 3.8). Operan así en faster-whisper (código transcribe.py, idéntico en lógica al de openai/whisper):
for t in temperature_tuple:
    decode_result = decode(segment, temperature=t)
    needs_fallback = False
    if decode_result.compression_ratio > compression_ratio_threshold:
        needs_fallback = True  # demasiada repetición
    if decode_result.avg_logprob < log_prob_threshold:
        needs_fallback = True  # confianza demasiado baja
    if (decode_result.no_speech_prob > no_speech_threshold
        and decode_result.avg_logprob < log_prob_threshold):
        # tratado como silencio: se devuelve vacío
        return EMPTY
    if not needs_fallback:
        break
Valores estándar del paper / openai/whisper / faster-whisper:
ParámetroDefaultRecomendado para tu casocompression_ratio_threshold2.42.4 (o 2.2 más agresivo)log_prob_threshold-1.0-1.0 (o -0.8 más agresivo)no_speech_threshold0.60.6 (o 0.5 más agresivo si tienes muchos falsos positivos de speech)temperature(0.0, 0.2, 0.4, 0.6, 0.8, 1.0)Discutido abajo
El paper de HuggingFace transformers recomienda compression_ratio_threshold = 1.35 para Whisper large-v3, que es más estricto. Para small con int8, bajarlo a 1.35 puede ser demasiado: dispararás fallbacks innecesarios. Empieza con 2.4 y considera 2.2 si sigues viendo repeticiones. Hugging Face
Punto importante: estos thresholds solo aplican a long-form transcription (cuando hay > 1 segmento de 30 s). En audio de 1–3 s con un único segmento, en la práctica se evalúan al final del segmento único, pero como condition_on_previous_text=False, el efecto se limita a (a) gatillar fallback a mayor temperatura y (b) detectar segmento como silencio.
1.4 Temperature y temperature fallback
Conforme al código de Whisper (openai/whisper/transcribe.py, líneas 102-128): cuando t > 0, beam search y patience se deshabilitan; solo cuando t == 0 el decoder hace beam search con beam_size. Para t > 0 se usa sampling con best_of (default 5).
Para tu caso (audio corto, idioma fijo, baja latencia):

Mantener una tupla mínima (0.0, 0.2, 0.4) (lo que ya tienes) está bien y es defensivo.
Si te preocupa latencia: usar solo temperature=0.0 (escalar, no tupla) elimina el fallback. Esto baja latencia pero pierdes el mecanismo de "rescate" cuando la decoding inicial produce repetición. En audios cortos es aceptable porque la repetición es rara; las alucinaciones cortas no se detectan por compression_ratio.
El GDELT Project documentó que temperature_increment_on_fallback=None estabiliza salidas en re-runs.

Trade-off concreto: con temperature=0.0 solo, la salida es determinista pero un mal beam search ocasional no se recupera. Con la tupla, ganas robustez pero el caso peor de latencia se multiplica por hasta 6. Para "Alexa-like", el patrón aceptado es temperature=0.0 (un solo intento) y descartar el resultado vía heurísticas post-hoc si falla.
1.5 condition_on_previous_text
Está correctamente puesto en False. La motivación está documentada en el issue #21467 de huggingface/transformers y la discussion #679 de openai/whisper. Con audio segmentado por wake-word y comandos independientes, no hay continuidad semántica entre sesiones de transcripción, así que False es estrictamente correcto. Mantenerlo en True con comandos cortos suele inducir repeticiones del tipo "Hey Gemma. Hey Gemma. Hey Gemma." cuando el modelo se queda enganchado.
1.6 without_timestamps=True vs False
Este es probablemente el cambio aislado de mayor impacto en tu sistema. Sanchit Gandhi (mantenedor de Whisper en HuggingFace transformers) publicó:

"Why does returning timestamps help Whisper reduce hallucinations? 🧐 Empirically, most practitioners have found that setting return_timestamps=True helps reduce hallucinations, particularly when doing long-form evaluation. My interpretation is that forcing the model to predict timestamps is contradictory to hallucinations. Suppose you have the transcription: 'The cat sat on the on the on the mat.' — once the model is forced to emit timestamp tokens, the repeated phrase doesn't align temporally and the decoder is pushed away from it."

Hay también un hallazgo curioso en linto-ai/whisper-timestamped issue #105: suprimir el token <|notimestamps|> (50364 en multilingüe, 50363 en english-only) elimina casi por completo las alucinaciones en clips de no-speech. Esto es coherente con la observación de Gandhi. GitHub
Trade-off real:

without_timestamps=False añade unos pocos tokens adicionales por segmento (overhead < 5 % en latencia con beam_size=1).
Los timestamps que devuelve Whisper son a nivel de segmento (no de palabra) y no necesitas usarlos. Solo necesitas que el decoder los genere.
Recomendación firme: cambiar a without_timestamps=False para tu pipeline. El impacto en latencia es trivial; el impacto en eliminación de alucinaciones es sustancial según múltiples observaciones empíricas.

1.7 El truco del initial_prompt para suprimir alucinaciones ("Um, hmm.")
Existe un truco folclórico, popularizado por el repo WhisperHallu y replicado en Reddit/Discord, consistente en usar initial_prompt="Um, hmm." o "Eh, este..." para "instalar" en el modelo un estilo conversacional de transcripción literal con disfluencias. La idea: el decoder, condicionado por un prompt que contiene muletillas, asume que estamos en un contexto de transcripción "verbatim" y reduce el sesgo hacia frases pulidas del corpus YouTube. La evidencia es anecdótica pero consistente (varios usuarios reportan mejoras).
Para tu caso, donde quieres priorizar comandos con vocabulario técnico, es mejor usar el initial_prompt para el vocabulary biasing (sección 2) que para muletillas. Pero puedes combinarlos:
pythoninitial_prompt = "Eh, oye. Hey Gemma, abre Steam, Spotify, Discord, VS Code, Chrome, YouTube y Netflix. Apaga la luz, sube el volumen."
1.8 Detección posterior de alucinaciones
Heurísticas comunes (post-decode) implementadas en proyectos como stable-ts, whisper-timestamped y el paper AGH 2501.11378:

Compression ratio del texto: len(text) / len(zlib.compress(text.encode('utf-8'))). Texto repetitivo da ratios > 2.4. La librería usa esto internamente pero puedes re-aplicarlo a nivel cliente con threshold más estricto (2.2 o incluso 1.8).
avg_logprob: faster-whisper expone segment.avg_logprob por segmento. Valores < -1.0 son sospechosos. Para comandos cortos, valores < -0.8 ya son cuestionables.
no_speech_prob: segment.no_speech_prob > 0.5 indica probable silencio mal transcrito.
Bag of Hallucinations (BoH): el paper AGH 2501.11378 publica una lista de las frases más alucinadas por Whisper-large-v3 en distintos idiomas. Para español, ver la siguiente sección sobre suppress_tokens. arxiv
Repetición patológica: detectar n-gramas repetidos (p. ej., misma frase de 3+ tokens apareciendo > 2 veces consecutivas) con no_repeat_ngram_size aplicado a posteriori sobre el texto.
Word count vs duración: si el clip dura 0.8 s y la transcripción es > 8 palabras, casi seguro es alucinación.

2. Biasing y prompting para reconocer comandos y nombres propios
2. Biasing y prompting para reconocer comandos y nombres propios
2.1 Cómo Whisper consume initial_prompt
El comportamiento real, conforme al código en faster_whisper/transcribe.py (función _get_prompt) y al paper:

El prompt se tokeniza con el tokenizer de Whisper.
Se inserta antes de la secuencia de tokens especiales (<|sot|><|es|><|transcribe|><|notimestamps|>), por lo que actúa como "transcripción previa imaginaria" que condiciona al decoder.
La capacidad máxima del contexto Whisper es 448 tokens, divididos en mitad input / mitad output. Solo se pueden usar ~224 tokens de prompt (faster-whisper aplica max_length // 2 - 1). GitHub + 2
Cuando hay hotwords además de initial_prompt, el prompt construido es: [prev_tokens_special] [hotwords_tokens] [initial_prompt_tokens] <|sot|> <|es|> .... Si la suma excede 224, faster-whisper trunca el prompt previo (no las hotwords). GitHub

Hallazgos empíricos importantes (OpenAI cookbook, ailia tech blog, discussion #117 de openai/whisper):

Prompts muy cortos (1–3 palabras) son poco efectivos. El modelo "no se entera" del estilo. Openai
Prompts naturales (frases completas) funcionan mejor que listas de palabras con comas, aunque ambas funcionan.
Prompts con estilos atípicos no se siguen (p. ej., texto ALL CAPS o con caracteres raros). Openai
Cambios pequeños en el prompt pueden producir cambios grandes en la salida (no es robusto). GitHub

2.2 Construcción de un initial_prompt óptimo para tu caso
Tienes dos objetivos simultáneos:

Sesgar el modelo hacia anglicismos técnicos (Steam, Spotify, Discord, VS Code, Chrome, YouTube, Netflix, etc.) con su grafía correcta en lugar de aproximaciones fonéticas españolas ("estímulo", "espotify").
Sesgar el estilo hacia comandos breves ("Hey Gemma, abre X" / "Gemma, sube el volumen") en lugar de prosa narrativa de YouTube.

Propuesta concreta validada con las recomendaciones de OpenAI Cookbook (multi-sentence, natural, longer prompts):
pythoninitial_prompt = (
    "Conversación con el asistente Gemma. "
    "Hey Gemma, abre Steam. Gemma, abre Spotify y reproduce música. "
    "Gemma, abre Discord, VS Code, Chrome, Firefox, YouTube, Netflix, "
    "Twitch, WhatsApp, Telegram, Visual Studio Code, Notepad, Explorer. "
    "Gemma, apaga la luz del salón. Gemma, enciende la luz de la cocina. "
    "Gemma, sube el volumen. Gemma, baja el volumen. Gemma, pausa la música. "
    "Gemma, pon el temporizador a cinco minutos. Gemma, qué hora es. "
    "Gemma, cómo está el tiempo en Madrid. Gemma, busca en Google. "
    "Gemma, escribe un correo. Gemma, cierra la ventana. "
    "Comandos breves, en español, dirigidos al asistente Gemma."
)
Notas:

Está en español natural con puntuación correcta — Whisper se ajusta al estilo.
Repite "Gemma" muchas veces para que el modelo aprenda que "Gemma" es una palabra esperada (no "Kema", "Quema", "Tema"). Este es el truco clave para resolver "Hey Kema!".
Incluye las apps con su grafía inglesa en un contexto natural. La guía oficial de OpenAI (cookbook) recomienda exactamente este patrón ("spelling guide"). Openai
Termina con una meta-descripción del estilo ("Comandos breves, en español...") para reforzar.
Cabe perfectamente en 224 tokens. Cuenta tokens con el tokenizer Whisper antes de fijarlo.

Posible refinamiento: rotar/personalizar la lista de apps según las que el usuario realmente usa. Si tu sistema sabe que el usuario solo usa Steam, Discord y VS Code, no metas Netflix ni YouTube (que pueden derivar a contenido tipo "youtube tutorial..." en alucinaciones).
2.3 El parámetro hotwords de faster-whisper
hotwords se añadió en faster-whisper 1.0.0 (PR #941, mediados 2024). El código en transcribe.py lo trata como un prompt adicional que se prepone después del prompt previo y antes del initial_prompt. Es decir, internamente hotwords es esencialmente un segundo initial_prompt, no un mecanismo de "shallow fusion" como en otros ASR. Esto está confirmado leyendo _get_prompt:
pythonif hotwords is not None and prefix is None:
    hotwords_tokens = tokenizer.encode(" " + hotwords.strip())
    if len(hotwords_tokens) >= self.max_length // 2:
        hotwords_tokens = hotwords_tokens[: self.max_length // 2 - 1]
    prompt.extend(hotwords_tokens)
 GitHub
Implicaciones prácticas:

hotwords no implementa contextual biasing real (no es un trie+shallow fusion estilo Kaldi/Conformer-CTC, ni un TCPGen). Eso requeriría modificar logits durante decoding, lo cual faster-whisper/CTranslate2 no expone.
Para fines prácticos en tu caso, hotwords y initial_prompt son redundantes: ambos sesgan al decoder via prepend de tokens. La diferencia es que hotwords se aplica también cuando hay condicionamiento por prev_text (carry across segments) mientras que initial_prompt solo en el primer segmento.
No los uses ambos: elige uno. Recomendación: usar hotwords con la lista exacta de palabras a sesgar (apps + nombre "Gemma") en formato lista, y dejar initial_prompt=None. O al revés.

Patrón recomendado para ti:
pythonhotwords = "Gemma Steam Spotify Discord Chrome Firefox YouTube Netflix Twitch VS Code Visual Studio Code WhatsApp Telegram"
Trabajos académicos (arXiv 2410.18363, "Contextual Biasing without Fine-Tuning") muestran reducciones del 20–40 % en WER de términos OOV usando prompting estructurado en Whisper. El paper concluye que para vocabularios pequeños (< 100 palabras), prompting es competitivo con fine-tuning.
2.4 suppress_tokens y la "Bag of Hallucinations" en español
Por defecto, suppress_tokens=[-1] en faster-whisper, lo que invoca la lista interna estándar de tokens no-speech (símbolos, paréntesis, caracteres especiales). Puedes extenderla con IDs de tokens específicos.
Frases típicas alucinadas en español por Whisper (recopilación de issues, foros, mi observación en discusiones de huggingface, AGH 2501.11378 y experiencia común):

Suscríbete al canal
No olvides darle like
Gracias por ver el video / Gracias por ver
Subtítulos realizados por la comunidad de Amara.org
Subtítulos por Aegisub
Hasta la próxima / Hasta el próximo video
Música (como literal, marca de subtítulo)
[Música], [Aplausos]
Hola a todos / Bienvenidos a este canal
Soy [nombre] y hoy os traigo
♪♪♪

Estrategia: suprimir los tokens individuales más distintivos. Para hacerlo correctamente:
pythonfrom faster_whisper.tokenizer import Tokenizer

tok = model.hf_tokenizer  # acceso al tokenizer interno
banned_phrases = [
    "Suscríbete", "suscríbete", "Gracias por ver",
    "Subtítulos", "Amara.org", "Aegisub",
    "♪", "♪♪", "♪♪♪"
]
banned_token_ids = set()
for phrase in banned_phrases:
    for tid in tok.encode(phrase, add_special_tokens=False):
        banned_token_ids.add(tid)
suppress_tokens = [-1] + sorted(banned_token_ids)
Advertencia importante (documentada en openai/whisper discussion #1873): suprimir tokens "comunes" como "I" (286), "Thank" (1044) en inglés rompe transcripciones legítimas. En español, "Gracias", "Hola", "Música" son palabras válidas en muchísimos contextos. Suprimir tokens completos a nivel de logit es agresivo y puede romper dictado largo. Una alternativa más segura es filtrado por substring a posteriori sobre el texto devuelto (sección 9). GitHub
Truco adicional documentado: suprimir el token <|notimestamps|> (50364 multilingüe) "fuerza" al modelo a emitir timestamps incluso si pediste without_timestamps=True, lo que en clips de no-speech reduce drásticamente alucinaciones (linto-ai/whisper-timestamped issue #105). En tu setup, mejor poner without_timestamps=False directamente. GitHub
2.5 Casos documentados de mejora con biasing

arXiv 2410.18363 (Lall & Liu, Singapore Polytechnic, 2024): biasing por prefix-tree sobre vocabulario marítimo, reducción notable de WER sin fine-tuning.
arXiv 2309.09552 (CB-Whisper, ICASSP 2024): contextual biasing + Open-Vocabulary Keyword Spotting sobre Whisper, hasta 80 % de mejora en recall de hot-words en Aishell.
arXiv 2502.11572 (B-Whisper, 2025): "biasing-Whisper" con prompts estructurados consigue 60.8 % de mejora en U-WER de palabras raras (Artie Bias, VoxPopuli).
OpenAI Whisper Cookbook: confirma oficialmente que prompts largos con grafías esperadas mejoran transcripción de nombres propios.

3. Beam size, temperature y parámetros de decoding
3. Beam size, temperature y parámetros de decoding
3.1 Beam size para audio corto en CPU
Datos relevantes:

En openai/whisper, beam_size default es 1 (greedy).
En faster-whisper, beam_size default es 5. Esta es la causa principal por la que las comparativas naive entre ambos suelen ser injustas. GitHub +2
El paper original de Whisper (Tabla 7) mostró que mover de greedy a beam search reduce WER pero con rendimientos decrecientes a partir de beam=5.
En CPU, el coste del beam search escala aprox. linealmente con beam_size porque cada step expande K hipótesis. Pasar de 5 a 1 reduce el coste del decoder ~3-5×.
En el paper AGH 2501.11378 (Tabla VI): la tasa de alucinaciones es menor con beam_size=1 que con beam_size=5 en clips no-speech / speech corto. Es contraintuitivo pero consistente: beam search puede "encontrar" hipótesis más probables del LM-prior (más alucinadas) que el greedy.

Recomendación para tu caso:
Modobeam_sizebest_ofJustificaciónComando corto (< 3 s)1 (greedy)n/aLatencia mínima, alucinaciones menoresDictado largo (> 3 s)5n/aAccuracy óptima, latencia tolerable
Implementación: detecta la duración antes de invocar Whisper y ajusta. Para una transición suave puedes hacer beam_size=3 como punto medio si quieres una sola configuración.
3.2 best_of
best_of solo aplica cuando temperature > 0 (sampling). Si tu temperature=(0.0, 0.2, 0.4), el fallback a 0.2 y 0.4 usaría best_of (default 5) para sampling. Si bajas a temperature=0.0 solo, best_of es irrelevante.
3.3 patience y length_penalty

patience (default 1.0): controla cuánto se espera para terminar beam search. Valores > 1.0 ralentizan; valores < 1.0 cortan antes. Para comandos cortos, patience=1.0 es correcto. Whisper API Docs
length_penalty (default 1.0): valores > 1 favorecen salidas largas, valores < 1 favorecen cortas. Para comandos cortos, considera length_penalty=0.5–0.8 para penalizar al beam search por emitir tokens extra (alucinaciones suelen ser texto añadido). Esto es defensivo: en pruebas reales puede o no ayudar; el impacto es modesto. Whisper API Docs

3.4 repetition_penalty / no_repeat_ngram_size
Estos parámetros, expuestos por CTranslate2 y propagados por faster-whisper, ayudan contra repeticiones patológicas:

repetition_penalty=1.1–1.2 aplica un factor de penalización a tokens ya generados. Pero rompe transcripciones legítimas con repeticiones naturales ("sí, sí, sí"). Úsalo solo si tienes repeticiones graves. Whisper API Docs
no_repeat_ngram_size=3 impide que un 3-grama se repita. Más robusto que repetition_penalty pero también puede romper transcripciones legítimas. Whisper API Docs

Para tu setup: dejarlos en defaults (1.0 y 0) salvo que detectes repeticiones patológicas. No son la herramienta correcta para tu problema (que son sustantivos inventados, no repeticiones).
3.5 Switch dinámico de configuración
Recomendación de arquitectura: dos perfiles de transcripción seleccionados por duración del audio:
pythondef get_transcribe_kwargs(audio_seconds: float):
    base = dict(
        language="es",
        condition_on_previous_text=False,
        vad_filter=False,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
        without_timestamps=False,   # CAMBIO CLAVE
        initial_prompt=INITIAL_PROMPT,
        hotwords=None,              # uno u otro, no ambos
        suppress_tokens=[-1],
    )
    if audio_seconds < 3.0:
        # Modo comando corto: latencia + estabilidad
        return {**base,
                "beam_size": 1,
                "best_of": 1,
                "temperature": 0.0,
                "length_penalty": 0.8}
    else:
        # Modo dictado largo: accuracy
        return {**base,
                "beam_size": 5,
                "best_of": 5,
                "temperature": (0.0, 0.2, 0.4),
                "length_penalty": 1.0}
4. ¿Es small la mejor opción para tu caso?
4. ¿Es small la mejor opción para tu caso?
4.1 Comparativa de modelos para español, CPU, int8
Datos consolidados de los benchmarks de SYSTRAN/faster-whisper README, Issue #1030, HuggingFace model cards, y ailia tech blog (medium.com/axinc-ai), más mediciones públicas en CPU comerciales:
ModeloParámetrosTamaño en disco (int8)RAM CPU típicaLatencia 1 s audio en CPU moderna (i7-12700K, 8 threads)WER es (CommonVoice 13)whisper-tiny39 M~75 MB~250 MB~120 ms~10–13 %whisper-base74 M~145 MB~330 MB~180 ms~7–9 %whisper-small244 M~470 MB~700 MB~400–600 ms~5–6 %whisper-medium769 M~1.5 GB~2.0 GB~1500–2200 ms~4 %whisper-large-v31550 M~3.0 GB~3.5 GB~3500–5000 ms~3.5 %whisper-large-v3-turbo809 M~1.6 GB~1.5 GB (int8)~1800–2500 ms~3.8–4.5 %distil-whisper-large-v3-es (marianbasti)~750 M~1.5 GB~1.5 GB~700–1200 ms (encoder pesado, decoder ligero)~5.1 % WER (modelo card, validación propia)
Notas críticas:

Los WER de la tabla son aproximados y pueden variar 1–2 puntos según dataset. CommonVoice 13 es referencia común pero no es representativo de "comandos cortos en casa con ruido". Para tu caso real, podrían empeorar.
Los tiempos asumen audio de 1 segundo. Whisper procesa internamente la ventana completa de 30 s en el encoder, así que la latencia tiene un componente fijo grande (encoder) y otro variable (decoder, proporcional al número de tokens emitidos). Para comandos cortos, el encoder domina.
Modelos basados en large-v3 turbo (turbo o distil-large-v3) tienen un encoder pesado (32 capas) pero un decoder ligero (4 capas). Resultado: en GPU son muy rápidos pero en CPU, el encoder cuesta caro (medium.com/axinc-ai benchmarks: turbo en CPU M2 toma 18 s por 40 s de audio vs small en 9 s — turbo es más lento que small en CPU). MediumHugging Face
distil-whisper-large-v3 oficial es solo inglés. La versión en español de marianbasti es un trabajo de la comunidad (Universidad Nacional de Río Negro + SandboxAI). Existe pero no es oficial de HuggingFace. GitHub +2Hugging Face

4.2 Conclusión sobre tamaño de modelo
Para tu hardware (6 GB VRAM se usan para Gemma, Whisper en CPU) y target Alexa-like (< 1 s):

whisper-small en CPU int8 es el sweet spot razonable. Latencia ~400–600 ms para comandos cortos en una CPU desktop moderna (Ryzen 5/7, i5/i7 de 12ª gen+).
whisper-medium en CPU int8 triplica la latencia (~1.5–2.2 s) — excede tu objetivo de subsegundo. Solo viable si la CPU es muy potente (i9/Ryzen 9 con 16+ threads).
whisper-tiny / base: tentadores por latencia, pero WER en español sube notablemente y las alucinaciones con OOV (Steam, Spotify) son peores que en small. No recomendado salvo que la CPU sea muy débil.
distil-whisper-large-v3-es de marianbasti: técnicamente interesante pero (a) calidad no oficial, (b) en CPU el encoder pesado lo hace más lento que small, (c) requiere convertirlo a CTranslate2 manualmente. No vale la pena para tu caso.
whisper-large-v3-turbo en CPU: no es viable para "Alexa-like" subsegundo. 2+ s en CPU.

Veredicto: mantén small con int8. El cuello de botella en tu caso no es el tamaño del modelo sino la falta de biasing y la entrega de audio sub-óptimo a Whisper.
Si después de implementar todas las mitigaciones de este reporte siguieras viendo accuracy insuficiente en comandos, una alternativa es ejecutar whisper-small con device="cuda" y compute_type="int8_float16": ocupa solo ~600 MB de VRAM (queda margen sobre tus 6 GB para Gemma) y la latencia baja a < 100 ms por comando. Habría que medir si convive bien con Gemma en VRAM, pero es una salida si el límite de CPU resulta insuficiente.
4.3 Quantization: int8 vs int8_float16 vs int8_float32 vs float16 en CPU
Documentación de CTranslate2 (motor de faster-whisper):

float32: precisión completa, sin cuantización. RAM máxima.
int8: pesos cuantizados a 8 bits con escalas float32. Recomendado para CPU. Casi cualquier CPU x86-64 moderna tiene VNNI/AVX2 que acelera int8 dramáticamente.
int8_float16: pesos int8, activaciones float16. Solo útil en GPU. En CPU, float16 no está acelerado en muchas CPUs (sí en AVX-512 con FP16 ext, no en AVX2). Puede ser más lento que int8 puro en CPU.
int8_float32: pesos int8, activaciones float32. En CPU moderna sin AVX-512 FP16, suele ser idéntico o muy similar a int8. CTranslate2 internamente usa float32 para las activaciones cuando el target es CPU sin FP16 nativo.
float16: pesos float16, activaciones float16. No recomendado en CPU salvo AVX-512_FP16 (CPUs Intel Sapphire Rapids+).

Recomendación firme para tu CPU x86-64 Windows 11: compute_type="int8" (lo que ya tienes). No te molestes con int8_float32 ni float16 a menos que tengas Intel Sapphire Rapids o AMD Zen5 con AVX-512.
4.4 Modelos especializados en comandos cortos
No existe un Whisper específico para comandos cortos en español (open source y compatible con CTranslate2). Las alternativas que no son Whisper:

Vosk (que ya usas para wake-word): excelente para vocabularios cerrados y reconocimiento de comandos. Modelo es-0.42 (~50 MB) es muy ligero y rápido. Idea arquitectónica: si los comandos son un set limitado (< 100 frases), podrías usar Vosk para el comando completo en lugar de Whisper, y reservar Whisper solo para dictado libre. Es el patrón que sigue Speech-to-Phrase en Home Assistant.
NVIDIA Parakeet / Canary: WER bajísimo y muy rápidos, pero solo inglés (Parakeet) o 4 idiomas limitados (Canary, sin español robusto). No aplicable. Hugging Face
Modelos de Wav2Vec2 finetuned en español (jonatasgrosman/wav2vec2-large-xlsr-53-spanish, p. ej.): buenos pero su WER en comandos cortos con OOV no supera a Whisper-small con biasing.

Sugerencia arquitectónica adicional: para los comandos, considera usar Speech-to-Phrase o un grammar-based recognizer (Vosk con KaldiRecognizer y vocab limitado) en paralelo a Whisper. Si Vosk produce una match high-confidence dentro de tu grammar, úsalo; si no, cae a Whisper. Esto resuelve el 80–90 % de los comandos en < 100 ms con 0 alucinaciones y reserva Whisper para casos abiertos.
5. VAD: ¿reintroducir o no?
5. VAD: ¿reintroducir Silero o no?
5.1 Por qué fallaba Silero VAD en tu setup
La razón documentada en faster-whisper issue #477 y prácticamente todas las discusiones recientes: los defaults de Silero VAD dentro de faster-whisper son muy distintos de los defaults del repo upstream snakers4/silero-vad:
ParámetroSilero upstreamfaster-whisper VADthreshold0.50.5min_speech_duration_ms250250 (varias versiones)min_silence_duration_ms1002000 (¡20× más conservador!)window_size_samples512 (32 ms)1024 (64 ms)speech_pad_ms30400 (¡13× más!)
El speech_pad_ms=400 de faster-whisper añade 400 ms antes y 400 ms después de cada chunk detectado por VAD. Esos 800 ms extra son tiempo añadido a cada transcripción y son responsables de una parte importante de la sensación de "lentitud" con VAD habilitado. Además, el min_silence_duration_ms=2000 requiere 2 s continuos de silencio para terminar un chunk, lo que en una frase con pausas naturales no funciona.
5.2 Alternativas
OpciónLatenciaCalidadComentariosSin VAD (tu setup actual)0BaselineMás alucinaciones por silencio inicial/finalSilero VAD v5 ajustado+20–80 msAltaBien tuneado, mejor opciónWebRTC VAD (py-webrtcvad)+5–10 msMediaMenos preciso pero ligerísimofaster-whisper vad_filter=True+200–800 ms (defaults), +50–100 ms (tuneado)AltaCómodo pero defaults malosSolo RMS (lo tuyo)0BajaRápido pero no filtra ruido bien
5.3 Estrategia híbrida recomendada
Tu endpoint actual por RMS funciona bien para latencia. No tires el RMS endpoint. Pero antes de pasar el buffer a Whisper, corre Silero VAD una sola vez sobre ese buffer para hacer un trim agresivo de silencios laterales:
python# Pseudocódigo
def trim_with_vad(audio_int16_16k, silero_vad):
    # Silero espera float32
    audio_f32 = audio_int16_16k.astype(np.float32) / 32768.0
    speech_chunks = silero_vad.get_speech_timestamps(
        audio_f32,
        threshold=0.5,
        min_speech_duration_ms=200,
        min_silence_duration_ms=200,
        window_size_samples=512,
        speech_pad_ms=100,   # <-- clave: mucho menos que 400
    )
    if not speech_chunks:
        return None  # rechazar, era silencio/ruido
    start = speech_chunks[0]["start"]
    end = speech_chunks[-1]["end"]
    return audio_int16_16k[start:end]
Beneficios:

Elimina silencio inicial y final → menos alucinaciones (causa #1 documentada).
Si el VAD no detecta speech, rechaza la transcripción entera antes de invocar Whisper → cero alucinaciones en falsos positivos del wake-word.
Latencia: Silero VAD v5 (silero_vad.onnx, ~1 MB) procesa 1 s de audio en ~15 ms en CPU. Negligible.
Mantienes tu RMS para detectar el fin de utterance (es más rápido para esa decisión binaria).

5.4 Configuración óptima de Silero VAD para tu caso
Si optas por usar silero-vad (mejor que vad_filter=True de faster-whisper, porque lo controlas tú):
pythonimport torch
from silero_vad import load_silero_vad, get_speech_timestamps

vad_model = load_silero_vad(onnx=True)  # ONNX en CPU es rapidísimo
torch.set_num_threads(1)  # importante en CPU

speech_ts = get_speech_timestamps(
    audio_float32,
    vad_model,
    sampling_rate=16000,
    threshold=0.5,             # 0.4 si tienes audio bajito; 0.6 si hay mucho ruido
    min_speech_duration_ms=200,
    min_silence_duration_ms=300,  # comandos cortos: pausas naturales son ~200-400 ms
    window_size_samples=512,
    speech_pad_ms=100,         # padding lateral mínimo, NO 400
)
5.5 ¿vad_filter=True integrado de faster-whisper?
Funcionalmente equivalente a hacerlo tú, pero con peores defaults. Si lo usas, sobreescribe los defaults:
pythonsegments, info = model.transcribe(
    audio, language="es",
    vad_filter=True,
    vad_parameters=dict(
        threshold=0.5,
        min_speech_duration_ms=200,
        min_silence_duration_ms=300,
        speech_pad_ms=100,
    ),
    ...
)
Pero hay una limitación real: con vad_filter=True y un comando ultracorto donde el VAD no encuentra speech, faster-whisper devolverá un generator vacío sin error. Bien para evitar alucinaciones, mal si el VAD es demasiado agresivo y bota commands legítimos.
Recomendación: VAD manual como pre-procesamiento (sección 5.3), no vad_filter=True, para tener control total sobre el comportamiento de rechazo.
6. Preprocesamiento de audio
6. Preprocesamiento de audio
Whisper espera mono float32 a 16 kHz normalizado a [-1, 1]. El feature extractor de OpenAI convierte ese array al log-mel spectrogram de 80 mel bins (128 en large-v3) sobre ventanas de 25 ms cada 10 ms, normalizando los mel features. Esto está fijado en el modelo y no es ajustable.
6.1 Resampling

16 kHz es obligatorio. Si llega 44.1 kHz o 48 kHz, hay que resamplear. PyAV (que faster-whisper usa internamente cuando le pasas un path o un bytes-like) hace esto automáticamente. Si le pasas un np.ndarray, debes resamplear tú previamente. GitHubPyPI
Para 16 kHz mono int16 (lo tuyo) la conversión es trivial: audio_f32 = audio_int16.astype(np.float32) / 32768.0.
Calidad del resampler importa. Usa scipy.signal.resample_poly o librosa.resample(res_type="kaiser_best") o soxr (mejor). Resamplers naive (interpolación lineal) introducen aliasing y degradan WER ~5–10 %.

6.2 Normalización
Whisper internamente normaliza el log-mel con medias y varianzas globales del entrenamiento. La amplitud absoluta del audio importa relativamente poco (el log compresor mitiga). Aún así, observaciones empíricas:

Peak normalization a -1 dBFS: ligeramente útil si el micrófono está bajito. No hace daño.
RMS normalize a -23 LUFS o similar: poco impacto en Whisper. No vale la pena.
No clipping: asegúrate que el audio nunca satura (peak == 1.0 exacto). Si hay clipping, hay distorsión que sí degrada Whisper.
DC offset removal: aplicar un highpass de orden 1 a ~30 Hz elimina DC offset. Útil si el ADC tiene bias. Sin efecto significativo si no lo tiene.

6.3 Filtros y ruido

High-pass a 80 Hz: elimina hum (50/60 Hz), rumble. Recomendado siempre. Costo: ~0.1 ms por chunk.
Noise gate previo: si lo tienes calibrado para tu micrófono, ayuda. Pero no agresivo porque puede comer principios de palabra.
Spectral noise reduction (noisereduce, RNNoise):

noisereduce: spectral gating clásico, calidad media, latencia ~100–200 ms por 1 s audio.
RNNoise: ML-based, calidad mucho mayor, latencia ~5–10 ms en CPU (es ligerísimo). Recomendado si el entorno es ruidoso.
Cuidado: ambos pueden introducir artefactos que confunden a Whisper. Hay reportes (whisper-timestamped, OpenAI community) de que noise reduction mal hecho empeora WER. Si lo aplicas, mide WER antes/después.
Para tu caso (probablemente entorno doméstico relativamente silencioso), empieza sin denoising. Solo añade RNNoise si detectas problemas con ruido de fondo.



6.4 Pipeline de preprocesamiento sugerido
pythonimport numpy as np
from scipy.signal import butter, sosfilt

# 1. Filtro high-pass 80 Hz (eliminar rumble/DC)
sos_hpf = butter(4, 80, btype="highpass", fs=16000, output="sos")

def preprocess_for_whisper(audio_int16_16k: np.ndarray) -> np.ndarray:
    # int16 -> float32 [-1, 1]
    audio = audio_int16_16k.astype(np.float32) / 32768.0
    # High-pass
    audio = sosfilt(sos_hpf, audio).astype(np.float32)
    # Peak normalize a -1 dBFS si está bajito (opcional)
    peak = np.max(np.abs(audio))
    if 0 < peak < 0.5:
        audio = audio * (0.89 / peak)  # -1 dBFS
    return audio
Esto añade < 2 ms por segundo de audio en CPU moderna. Negligible.
6.5 ¿Audio 16 kHz exacto importa?
Sí, estrictamente. Si entregas 24 kHz a Whisper pensando "es similar", el log-mel se construirá mal porque las frecuencias de las mel bands son fijas en muestreo a 16 kHz. PyAV resamplea automáticamente cuando le das un archivo, pero si pasas array numpy, es tu responsabilidad. Verifica con assert sample_rate == 16000.
7. Acoustic snapshot y manejo del audio post wake-word
7. Acoustic snapshot y manejo de audio post wake-word
7.1 El problema concreto: "gemma apaga la luz" sin pausa
Tu acoustic snapshot envía a Whisper el audio completo [gemma apaga la luz], lo cual es lo correcto. El problema observado ("Hey Kema!", "Hey, Gemma! Ahora es Tim!") tiene dos componentes:

"Gemma" como palabra OOV: Whisper-small no conoce "Gemma" como nombre. Sin biasing, lo aproxima a la palabra española más cercana foneticamente. Solución: initial_prompt/hotwords con "Gemma" repetido varias veces (sección 2).
Wake-word concatenado con comando ultracorto sin pausa: el modelo no segmenta bien y la coarticulación deforma "steam" → "estímulo" / "Tim".

7.2 Estrategia óptima de snapshot
Cuatro patrones documentados en la literatura de asistentes (Alexa Wake-On-Voice paper, Google Hotword paper, Mycroft AI/OVOS docs):
A. Pasar el snapshot completo + sufijo, dejar wake-word en la transcripción y strip-arlo después (lo que tú haces hoy):

Ventaja: Whisper tiene contexto temporal completo, mejor segmentación.
Desventaja: si Whisper interpreta mal "Gemma" → "Tema", el split posterior falla.

B. Cortar inmediatamente después del fin del wake-word según Vosk, pasar solo el comando:

Ventaja: limpio, sin contaminación del wake-word.
Desventaja: pierdes contexto. Comandos ultracortos ("abre Steam") quedan en 0.5 s y Whisper alucina más por brevedad.

C. Pasar el snapshot completo con prefix_audio de algunos ms de silencio al inicio:

Variante actual tuya. Funciona aceptablemente. El padding inicial debe ser corto (50–100 ms), no largo.

D. Pasar snapshot completo + usar prefix (no prefix_audio) con la palabra "Gemma," como token prefix forzado:

En faster-whisper, prefix="Gemma," fuerza al decoder a empezar con esos tokens, lo que ancla el reconocimiento. Esto es muy potente. El código de _get_prompt lo soporta:

pythonif prefix:
    prefix_tokens = tokenizer.encode(" " + prefix.strip())
    ...
    prompt.extend(prefix_tokens)
 GitHub

Ventaja: garantizas que Whisper "espera" empezar con "Gemma," y el reconocimiento del resto se ancla. Muy útil cuando sabes que el wake-word disparó.
Desventaja: si el usuario no dijo realmente "Gemma" sino "Pemma" o similar, Whisper se inventa contexto. Funciona bien cuando el wake-word detector es fiable.

Recomendación combinada:
pythonsegments, info = whisper.transcribe(
    snapshot_audio,
    language="es",
    initial_prompt=INITIAL_PROMPT,   # contiene "Gemma" muchas veces
    prefix="Hey Gemma,",              # ancla fuerte
    beam_size=1,
    temperature=0.0,
    without_timestamps=False,
    condition_on_previous_text=False,
)
# Tras transcribir, hacer strip del prefijo
text = segments[0].text.strip()
text = re.sub(r"^\s*(hey\s*)?gemma[\s,!.]*", "", text, flags=re.IGNORECASE).strip()
prefix solo funciona en la primera ventana. Como tu audio es < 30 s, no es problema.
7.3 Cómo lo manejan los grandes (Alexa, Google, Siri)
Públicamente documentado:

Alexa (Amazon Wake On Voice paper, Interspeech 2018): hacen un speech onset detection basado en CNN sobre las features de wake-word. Cortan el audio justo al final del wake-word (con un padding de 100–200 ms hacia adelante). Luego pasan el resto al ASR cloud-side. La razón es que el wake-word ya lo procesó el detector dedicado y no hace falta re-procesarlo en el ASR generalista.
Google "Hey Google": similar, con dos modelos en serie. El segundo modelo confirma el wake-word con un audio extendido y luego corta.
Siri: usan dos VAD models en cascada (low-power, high-precision).

El patrón común es: el wake-word detector indica fin del wake-word, un VAD de speech detecta inicio del comando real, el ASR ve solo el comando. No pasan el wake-word al ASR.
7.4 Mejor patrón concreto para tu Gemma Stack
Combinación que recoge lo mejor:
1. Vosk detecta "gemma" / "hey gemma" → marca tiempo T_wake_end
2. Ring buffer: extraer audio desde T_wake_end - 50ms (margen pequeño) hasta endpoint RMS
3. Silero VAD trim del buffer (sección 5):
   - Si no hay speech detectado → rechazar, no invocar Whisper
   - Si hay → trim a chunks de speech con speech_pad_ms=100
4. Asegurar duración mínima 0.4 s (rellena con 100 ms silencio al final si es menor)
5. Pasar a Whisper SIN el wake-word, con:
   - initial_prompt = "...Hey Gemma, abre Steam... Gemma, apaga la luz..."
   - prefix = None  (porque ya cortamos el wake-word)
   - O alternativamente: dejar el wake-word, prefix="Hey Gemma,", y strip-ear texto.
¿Cuál ganador A vs D? Empíricamente:

Si tu wake-word detector (Vosk) tiene high precision (~95 %+) y los timestamps son fiables, patrón A (cortar) gana: sin contaminación del wake-word, transcripción limpia.
Si los timestamps de Vosk son ruidosos o el wake-word a veces corta principios de palabra, patrón D (prefix forzado) gana.

Vosk small es-0.42 tiene precision/recall buenos pero los timestamps a nivel de palabra pueden tener ±100 ms de incertidumbre. Por seguridad, recomiendo patrón A con un margen de seguridad (cortar 50 ms antes del fin reportado de "gemma" para no comer el inicio del comando).
7.5 Padding al inicio del snapshot

0–50 ms está bien (margen contra cortar inicio de palabra).
>200 ms es contraproducente (alucinaciones por silencio inicial).
No insertes silencio "para que Whisper entienda mejor". Whisper hace su propio padding interno con ceros hasta 30 s.

7.6 Pasar wake-word al Whisper sí o no — veredicto
OpciónRecomendaciónJustificaciónCortar wake-word y pasar solo comandoPreferidaComo Alexa/Google. Menos confusión OOV.Pasar todo + strip "gemma" del textoAceptableMás simple, funciona si initial_prompt tiene "Gemma".Pasar todo + prefix="Hey Gemma,"AceptableAncla fuerte, requiere wake-word fiable.Pasar todo sin ningún tratamientoNo recomendableProduce "Hey Kema!", el caso que reportas.
8. Modo dual: comandos cortos vs dictado largo
8. Modo dual: comandos cortos vs dictado largo
8.1 ¿Conviene tener dos configuraciones?
Sí, claramente. Los requisitos son antagónicos:
AspectoComando cortoDictado largoLatencia objetivo< 1 s< 1×RT (faster than real-time)Audio típico0.5–3 s5 s – minutosRiesgo principalAlucinación (inventar texto)Repeticiones, drift entre segmentosBeam search beneficiaPocoSíTemperature fallbackPierde tiempoÚtilVocabulary biasing necesarioAltoBajo (contexto natural)
8.2 Cómo decidir "esto va a ser corto" a priori

Tras endpoint RMS: la duración del audio ya está medida. Si dur < 3 s → corto.
Heurística estado-asistente: si el usuario invocó wake-word "gemma" y luego habló de inmediato (sin marcador de "dictado"), asume corto.
Comando explícito: tener wake-words distintos: "Gemma" para comandos, "Gemma dictado" o un slider en UI para dictado. Esto es muy útil porque el usuario sabe lo que va a hacer.

8.3 Implementación
Tu wrapper ya recibe el audio y conoce su duración. Switchea kwargs según duración (ver sección 3.5). En código:
pythonclass GemmaSTT:
    def __init__(self):
        self.model = WhisperModel("small", device="cpu", compute_type="int8",
                                  cpu_threads=N_PHYSICAL_CORES, num_workers=1)
        self._warmup()

    def _warmup(self):
        # Forzar JIT/kernel cache con un audio dummy
        dummy = np.zeros(16000, dtype=np.float32)
        _ = list(self.model.transcribe(dummy, language="es", beam_size=1)[0])

    def transcribe_command(self, audio_f32):
        return self._do_transcribe(audio_f32, mode="short")

    def transcribe_dictation(self, audio_f32):
        return self._do_transcribe(audio_f32, mode="long")

    def _do_transcribe(self, audio_f32, mode):
        dur = len(audio_f32) / 16000
        if mode == "short" or dur < 3.0:
            kwargs = SHORT_KWARGS
        else:
            kwargs = LONG_KWARGS
        segments, info = self.model.transcribe(audio_f32, **kwargs)
        return list(segments)
8.4 Posible refinamiento adicional
Para el modo corto, puedes precomputar el log-mel del initial_prompt (si Whisper lo permitiera) o mantener el modelo y prompt cacheados para amortizar coste. Faster-whisper no expone API para caching del KV pero el coste del prompt en clips cortos es despreciable (~50 tokens).
Más interesante: si tienes una sospecha muy fuerte de que el comando pertenece a un set cerrado (p. ej., "abre X" donde X ∈ {Steam, Spotify, ...}), puedes usar prefix="abre " para forzar el inicio del decoder y solo dejar libre el nombre de la app. Esto es muy efectivo. Algunos lo llaman "skill prefix biasing":
python# Si detectaste "abre" en la primera transcripción, re-pasa con prefix
prefix_attempts = ["", "abre ", "apaga la ", "enciende la ", "sube el ", "baja el "]
# Probar greedily la primera transcripción y, si tiene baja confidence, re-intentar con prefix
Esto pasa a ser un mini-grammar matcher y es probablemente mejor implementarlo como post-processing fuzzy match sobre la salida de Whisper contra un grammar de comandos (ver sección 9).
9. Detección y rechazo de alucinaciones post-transcripción
9. Detección y rechazo de alucinaciones post-transcripción
9.1 Lista de frases-veneno en español
Bag of Hallucinations típico para Whisper en español, compilado de issues GitHub, AGH 2501.11378 (BoH method), Calm-Whisper figura 1, y observaciones de la comunidad:
pythonSPANISH_HALLUCINATION_PHRASES = [
    # Subtítulos / YouTube outros
    "suscríbete",
    "no olvides darle like",
    "dale like",
    "gracias por ver",
    "gracias por ver el video",
    "hasta la próxima",
    "hasta el próximo video",
    "subtítulos realizados por la comunidad de amara.org",
    "subtítulos por la comunidad de amara",
    "subtítulos creados por la comunidad",
    "amara.org",
    "subtitulado por",
    "aegisub",
    # Saludos genéricos
    "hola a todos",
    "bienvenidos a este canal",
    "bienvenidos al canal",
    "qué tal amigos",
    # Música / aplausos
    "música",
    "[música]",
    "[aplausos]",
    "♪",
    # Tags varios
    "buenas",
    "buenos días a todos",
]

def looks_like_hallucination(text: str) -> bool:
    t = text.lower().strip().rstrip(".!?¡¿,;: ")
    for phrase in SPANISH_HALLUCINATION_PHRASES:
        if phrase in t and len(t) < len(phrase) + 20:
            return True
    return False
9.2 Heurísticas numéricas
Usar los metadatos de segment que faster-whisper expone:
pythondef quality_check(segment, audio_duration_s: float) -> tuple[bool, str]:
    text = segment.text.strip()
    if not text:
        return False, "empty"
    # 1. avg_logprob: confidence
    if segment.avg_logprob is not None and segment.avg_logprob < -1.0:
        return False, f"low_logprob ({segment.avg_logprob:.2f})"
    # 2. no_speech_prob
    if segment.no_speech_prob > 0.6:
        return False, f"no_speech ({segment.no_speech_prob:.2f})"
    # 3. compression_ratio (texto repetitivo)
    if segment.compression_ratio > 2.4:
        return False, f"repetitive ({segment.compression_ratio:.2f})"
    # 4. word density vs duración
    n_words = len(text.split())
    if audio_duration_s < 1.5 and n_words > 8:
        return False, f"too_many_words ({n_words} in {audio_duration_s:.1f}s)"
    if audio_duration_s < 0.7 and n_words > 4:
        return False, f"too_many_words_short ({n_words} in {audio_duration_s:.1f}s)"
    # 5. bag of hallucinations
    if looks_like_hallucination(text):
        return False, "BoH_match"
    # 6. n-gram repetition
    words = text.lower().split()
    if len(words) >= 6:
        for n in (2, 3):
            ngrams = [tuple(words[i:i+n]) for i in range(len(words)-n+1)]
            if len(ngrams) - len(set(ngrams)) > 2:
                return False, f"ngram_repeat_{n}"
    return True, "ok"
9.3 Reintento en caso de detección
Si la transcripción inicial falla quality_check, hay dos opciones:
A. Reintentar con temperatura distinta:
pythonfor temp in (0.0, 0.4, 0.8):
    segments, _ = model.transcribe(audio, temperature=temp, ...)
    seg = list(segments)[0] if segments else None
    if seg and quality_check(seg, dur)[0]:
        return seg.text
return None  # fail, ask user to repeat
B. Rechazar y pedir repetición al usuario (más Alexa-like): "Perdona, no te he entendido".
Recomendación: opción B primero. Reintentar con temperaturas distintas añade latencia (multiplica el tiempo) y rara vez "recupera" una alucinación severa. La UX de "perdón, repítelo" es preferible a una acción incorrecta sobre el sistema.
9.4 Fuzzy matching contra grammar de comandos
Para los comandos del asistente (lista cerrada conocida), un post-step muy efectivo:
pythonimport difflib

COMMANDS_TEMPLATES = [
    "abre {app}", "cierra {app}", "apaga la luz", "enciende la luz",
    "sube el volumen", "baja el volumen", "pausa la música", "qué hora es",
    ...
]

def match_command(transcript: str, threshold=0.75) -> Optional[str]:
    transcript_norm = transcript.lower().strip().rstrip("¡!¿?,.;: ")
    best_score, best_match = 0, None
    for template in expand(COMMANDS_TEMPLATES):
        score = difflib.SequenceMatcher(None, transcript_norm, template).ratio()
        if score > best_score:
            best_score, best_match = score, template
    return best_match if best_score >= threshold else None
Esto te permite resolver "abre estímulo" → match con "abre Steam" si están suficientemente cerca (sequence ratio ~0.7). Para nombres propios, usar una distancia fonética en lugar de char-level (Soundex español, Metaphone) es más robusto. Existe Metaphone en phonetics o jellyfish.
Patrón compuesto:

Whisper devuelve texto.
Quality check numérico — si falla, rechaza.
Si la app a la que apunta el usuario está en lista cerrada de skills → fuzzy match.
Si todos los matches están bajo threshold, pasa el texto crudo al LLM Gemma (modo conversación libre).

10. Optimizaciones CPU específicas para faster-whisper
10. Optimizaciones CPU específicas para faster-whisper
10.1 cpu_threads y num_workers
CTranslate2 (motor) está optimizado con OpenMP, oneDNN y AVX2/AVX-512 cuando están disponibles. Configuración:

cpu_threads: número de threads que CTranslate2 usa intra-op (paralelismo dentro de una transcripción). Default 4 si no se especifica. Si tu CPU tiene N cores físicos, el óptimo está en N o N-2 cores físicos (no logical/hyperthreads).
num_workers: número de modelos paralelos cargados para procesar requests en paralelo. Para un asistente single-user, deja en 1. Más workers solo ayudan con batching de múltiples requests concurrentes.

Issue #133 de faster-whisper confirma: en CPU, incrementar cpu_threads más allá del número de cores físicos suele empeorar por context switching. Hay un sweet spot.
CPUs Intel híbridas (12ª/13ª gen, P-cores + E-cores): mejor pin a P-cores con cpu_threads = num_P_cores y dejar afinidad de proceso a esos cores. En Python:
pythonimport os, psutil

# Para CPU típica 8 cores físicos / 16 threads (no híbrida)
N_PHYSICAL = psutil.cpu_count(logical=False)
CPU_THREADS = max(4, N_PHYSICAL - 2)  # dejar 2 cores para Gemma y el resto del sistema

model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8",
    cpu_threads=CPU_THREADS,
    num_workers=1,
)

# También respeta OMP_NUM_THREADS para librerías auxiliares (numpy, scipy)
os.environ["OMP_NUM_THREADS"] = str(CPU_THREADS)
Caveat importante: el LLM Gemma corre en GPU pero puede tener pre/post-processing en CPU. Si tu pipeline ejecuta Whisper+Gemma simultáneamente, deja headroom para Gemma. Probar con cpu_threads = N_physical // 2 puede ser razonable.
10.2 CTranslate2 tuning
Variables de entorno útiles documentadas en CTranslate2 docs:
bashOMP_NUM_THREADS=8           # OpenMP threads (oneDNN, MKL fallback)
CT2_VERBOSE=0
CT2_USE_MKL=1               # solo si tienes MKL instalado
CT2_FORCE_CPU_ISA=AVX2      # forzar set de instrucciones si autodetect falla
CTranslate2 detecta automáticamente AVX2/AVX-512/NEON. En Windows 11 sobre x86-64 moderna esto "just works".
10.3 int8 en CPU x86-64 — detalles

AVX2 acelera int8 GEMM via VNNI emulado o int8 dot product. Speedup ~2-3× vs float32 puro.
AVX-512 VNNI (Cascade Lake+, Zen4+): int8 VNNI nativo. Speedup ~4-5× vs float32.
AVX-512 BF16/FP16 (Sapphire Rapids+, Zen5): aceleración adicional para int8_float16, pero como dijimos, raro en escritorio.

Concusión: compute_type="int8" es lo correcto y suficiente para tu hardware. No te molestes con variantes.
10.4 Warmup del modelo
La primera transcripción es ~2-3× más lenta por:

Carga de pesos a memoria (~470 MB para small int8).
Construcción de kernels JIT en CTranslate2 / oneDNN.
Inicialización del feature extractor.

Recomendado: warmup explícito al iniciar el servicio:
pythondef warmup_model(model):
    # 1 s de silencio (suficiente para inicializar grafos sin disparar BoH)
    dummy = np.zeros(16000, dtype=np.float32)
    segments, _ = model.transcribe(dummy, language="es", beam_size=1, temperature=0.0)
    _ = list(segments)
    # Y un audio "real" corto para asegurar paths habituales
    # (opcional: usar un wav grabado de "hola")
Tras warmup, latencias estables.
10.5 Reuso del modelo entre transcripciones
WhisperModel es thread-safe a nivel de transcribe() si num_workers >= número de threads concurrentes. Para un asistente single-stream, mantén una sola instancia del modelo cargada y reutilízala. No hay state que limpiar entre transcripciones cuando condition_on_previous_text=False. Esto es lo correcto.
Si invocas transcribe() concurrentemente desde varios threads con num_workers=1, las llamadas se serializan (no es problema en tu caso single-user).
10.6 Sobre BatchedInferencePipeline
faster-whisper >= 1.0.0 expone BatchedInferencePipeline que paraleliza chunks de un mismo audio largo. No aplica a tu caso (audio corto, una transcripción a la vez). No lo uses; añade overhead.
10.7 Resumen de optimizaciones CPU concretas
pythonimport os
import psutil
from faster_whisper import WhisperModel

N_PHYSICAL = psutil.cpu_count(logical=False)
CPU_THREADS = max(4, min(8, N_PHYSICAL - 2))   # ej. 6 en 8-core, 8 en 12-core

os.environ["OMP_NUM_THREADS"] = str(CPU_THREADS)

model = WhisperModel(
    model_size_or_path="small",
    device="cpu",
    compute_type="int8",
    cpu_threads=CPU_THREADS,
    num_workers=1,
    download_root="./models",
    local_files_only=False,
)

# Warmup
_dummy = np.zeros(16000, dtype=np.float32)
list(model.transcribe(_dummy, language="es", beam_size=1, temperature=0.0)[0])
11. Casos de estudio y proyectos similares
11. Casos de estudio y proyectos similares
11.1 Home Assistant + Wyoming + faster-whisper
Configuración por defecto del add-on Whisper de Home Assistant (home-assistant/addons/whisper/DOCS.md y rhasspy/wyoming-faster-whisper):

Default model: tiny-int8 en ARM (Raspberry Pi 4), base-int8 en otras plataformas.
auto para idioma (con la advertencia de que ralentiza).
Beam size: lo que faster-whisper traiga por defecto (5), no lo customizan.
VAD: faster-whisper integrado con defaults (no tuneados).

Lección: para Home Assistant a escala (Raspberry Pi 4), tiny o base con int8 y mucha tolerancia. Para hardware decente (Intel NUC), pasa a small/medium y obtiene ~1 s de latencia.
Importante también: HA introdujo Speech-to-Phrase (https://www.home-assistant.io/voice_control/voice_remote_local_assistant/) como alternativa cerrada a Whisper para reducir latencia. Speech-to-Phrase transcribe "lo que conoce" (un set cerrado de frases preconfiguradas) y es mucho más rápido y sin alucinaciones. Para tu skill set de comandos sería ideal complementarlo a Whisper.
Cita textual de su documentación:

"Speech-to-Phrase is a close-ended speech model. It transcribes what it knows. Extremely fast transcription even on a Home Assistant Green or Raspberry Pi 4 (under one second). Only supports a subset of Assist's voice commands."

11.2 Rhasspy / Wyoming protocol
Rhasspy 2.5 usaba Kaldi/Pocketsphinx con grammar files (closed-vocab) y obtenía latencia < 200 ms con accuracy alta en comandos. Su sucesor (Rhasspy 3 / Wyoming) ofrece ambos: Whisper para open vocab y Speech-to-Phrase para closed vocab.
Lección de Rhasspy: cuando el dominio es conocido, un grammar-based recognizer aplasta a Whisper en latencia y robustez.
11.3 Mycroft / OVOS
OVOS (OpenVoiceOS, sucesor de Mycroft) usa por defecto Mimic 3 para TTS y permite varios backends STT, recomendando faster-whisper o Vosk. Sus docs mencionan explícitamente que para comandos cortos prefieren Vosk con vocab limitado, y reservan Whisper para "intents libres".
11.4 Willow Voice Assistant
Willow (https://github.com/heywillow/willow) corre Whisper en ESP-BOX hardware con tiny o base y procesa en un servidor con medium o large. Latencias declaradas < 500 ms end-to-end gracias a:

Hardware AEC/AGC dedicado.
VAD on-device.
Server-side medium con int8 en GPU dedicada.

No usan faster-whisper en CPU. No es modelo aplicable a tu caso porque dependen de GPU server-side.
11.5 WhisperX, whisper.cpp, insanely-fast-whisper

WhisperX (m-bain/whisperX): añade alignment word-level y diarization sobre faster-whisper. No aplica para comandos cortos (es para podcasts/diarization de larga duración).
whisper.cpp (ggml-org): C++ con GGML, similar a CTranslate2 en CPU. Performance comparable a faster-whisper. No expone hotwords con la misma API; usa --prompt. La opción --suppress-non-speech-tokens se desactivó por defecto (commit citado de sourcehut/fitzsim) precisamente porque "causaba hallucinations al final del audio" como 'Thank you for listening'.
insanely-fast-whisper: batching agresivo sobre HF transformers. Solo GPU, no aplica a CPU.

Lección de whisper.cpp: el flag --suppress_tokens 50364 (suprimir el token notimestamps) es efectivo contra alucinaciones en clips de silencio. Confirma el hallazgo de Gandhi sobre la utilidad de without_timestamps=False.
11.6 Issues relevantes para tu caso (referencias rápidas)

openai/whisper #1606 "Hallucination on audio with no speech": discusión amplia. Solución base: VAD pre, suppress, condition_on_previous_text=False.
openai/whisper #1783 "Whisper Models are Poisoned?": copyright loops, sugiere VAD + int8 → float16 (no aplica en tu CPU caso pero útil como referencia).
openai/whisper #1873 "Share your hallucinations here": colección de samples por idioma con configuraciones que reducen.
openai/whisper #679 "A possible solution to Whisper hallucination": el origen de muchas mitigaciones folclóricas (silenceremove ffmpeg, WhisperHallu, etc.).
openai/whisper Discussion #117 "prompt vs prefix in DecodingOptions": explica diferencia.
openai/whisper Discussion #1477 "How to solve the issue of hot words?": prompts naturales con proper nouns.
SYSTRAN/faster-whisper #474 "adding initial_prompt is changing the segment duration": comportamiento del prompt en segmentación.
SYSTRAN/faster-whisper #1030 "Benchmark faster whisper turbo v3": números concretos de WER/latencia.
SYSTRAN/faster-whisper #477 "why faster-whiser vad default parameters are much different from silero-vad": muy relevante para tu reintroducción de VAD.
SYSTRAN/faster-whisper PR #965 "Set CPU threads according to the machine": discute óptimo de cpu_threads.
huggingface/transformers #21467 "Whisper: Decode with condition_on_previous_text=False": confirma su efecto antialucinación.

12. Recomendación final concreta
12. Recomendación final concreta
12.1 Lista priorizada de cambios a implementar (mayor a menor impacto)
RankCambioImpacto esperadoCoste1Añadir initial_prompt con "Gemma" y nombres de apps repetidos, en español naturalAlto. Resuelve "Hey Kema!" y "abre estímulo"0, solo configuración2Cambiar without_timestamps=FalseAlto. Reduce alucinaciones globales+5 % latencia3Pre-trim del buffer con Silero VAD (eliminar silencio lateral) + rechazar si no hay speechAlto. Elimina alucinaciones por silencio+20 ms latencia4Bajar beam_size a 1 + temperature=0.0 para modo comando cortoMedio-alto. Reduce alucinaciones + baja latenciaNegativa (mejora)5Cortar wake-word "gemma" antes de Whisper (no mandárselo)Medio-alto. Resuelve OOV del wake-wordBajo6Quality-check + Bag of Hallucinations post-transcripción + rechazoMedio. Atrapa lo que escapeBajo7Fuzzy match a comandos conocidos ("abre estímulo" → "abre Steam")Medio (para skills)Medio8High-pass 80 Hz + peak-normalize si bajitoBajo-medioNegligible9cpu_threads = N_physical - 2, warmup explícitoBajo (afina latencia, no accuracy)Bajo10Considerar Speech-to-Phrase / Vosk en paralelo a Whisper para skills cerradasAlto si los comandos son acotadosAlto (arquitectura)
12.2 Configuración exacta sugerida
12.2.1 Carga del modelo
pythonimport os
import numpy as np
import psutil
from faster_whisper import WhisperModel

N_PHYSICAL = psutil.cpu_count(logical=False) or 4
CPU_THREADS = max(4, min(8, N_PHYSICAL - 2))
os.environ["OMP_NUM_THREADS"] = str(CPU_THREADS)

model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8",
    cpu_threads=CPU_THREADS,
    num_workers=1,
    download_root="./models",
)

# Warmup
_dummy = np.zeros(16000, dtype=np.float32)
list(model.transcribe(_dummy, language="es", beam_size=1, temperature=0.0)[0])
12.2.2 Prompts y suppress_tokens
pythonINITIAL_PROMPT = (
    "Conversación con el asistente Gemma. "
    "Hey Gemma, abre Steam. Gemma, abre Spotify y reproduce música. "
    "Gemma, abre Discord, VS Code, Chrome, Firefox, YouTube, Netflix, "
    "Twitch, WhatsApp, Telegram, Visual Studio Code, Notepad, Explorer, OBS. "
    "Gemma, apaga la luz del salón. Gemma, enciende la luz de la cocina. "
    "Gemma, sube el volumen. Gemma, baja el volumen. Gemma, pausa la música. "
    "Gemma, pon el temporizador a cinco minutos. Gemma, qué hora es. "
    "Gemma, cómo está el tiempo en Madrid. Gemma, busca en Google. "
    "Gemma, cierra la ventana. Gemma, minimiza la ventana. "
    "Comandos breves en español dirigidos al asistente Gemma."
)

# Suppress tokens: la lista interna de no-speech tokens (-1 = default)
# más algunos tokens específicos de spanish YouTube outro
def build_suppress_tokens(hf_tokenizer):
    banned_substrings = [
        "Suscríbete", "suscríbete",
        "Amara.org", "amara.org",
        "♪",
    ]
    extra_ids = set()
    for s in banned_substrings:
        ids = hf_tokenizer.encode(s, add_special_tokens=False)
        # Solo añadir tokens >largos y específicos< (3+ caracteres en el decoded)
        for tid in ids:
            decoded = hf_tokenizer.decode([tid])
            if len(decoded.strip()) >= 4:
                extra_ids.add(tid)
    return [-1] + sorted(extra_ids)

SUPPRESS_TOKENS = [-1]  # empezar simple, añadir más solo si quality-check no es suficiente
12.2.3 Pipeline de preprocesamiento
pythonfrom scipy.signal import butter, sosfilt

sos_hpf = butter(4, 80, btype="highpass", fs=16000, output="sos")

def preprocess(audio_int16: np.ndarray) -> np.ndarray:
    audio = audio_int16.astype(np.float32) / 32768.0
    audio = sosfilt(sos_hpf, audio).astype(np.float32)
    peak = float(np.max(np.abs(audio)))
    if 0 < peak < 0.5:
        audio = audio * (0.89 / peak)
    return audio
12.2.4 VAD trim (opcional pero muy recomendado)
python# pip install silero-vad
from silero_vad import load_silero_vad, get_speech_timestamps
import torch

torch.set_num_threads(1)
vad = load_silero_vad(onnx=True)

def vad_trim(audio_f32: np.ndarray) -> np.ndarray | None:
    ts = get_speech_timestamps(
        audio_f32, vad, sampling_rate=16000,
        threshold=0.5, min_speech_duration_ms=200,
        min_silence_duration_ms=300,
        window_size_samples=512, speech_pad_ms=100,
    )
    if not ts:
        return None  # rechazar: no speech detectado
    start = ts[0]["start"]
    end = ts[-1]["end"]
    return audio_f32[start:end]
12.2.5 Transcripción (modo dual)
pythonSHORT_KWARGS = dict(
    language="es",
    task="transcribe",
    beam_size=1,
    best_of=1,
    patience=1.0,
    length_penalty=1.0,
    temperature=0.0,
    compression_ratio_threshold=2.4,
    log_prob_threshold=-1.0,
    no_speech_threshold=0.6,
    condition_on_previous_text=False,
    initial_prompt=INITIAL_PROMPT,
    prefix=None,
    suppress_blank=True,
    suppress_tokens=SUPPRESS_TOKENS,
    without_timestamps=False,   # CAMBIO CLAVE vs tu configuración actual
    vad_filter=False,            # hacemos VAD a mano antes
)

LONG_KWARGS = dict(
    language="es",
    task="transcribe",
    beam_size=5,
    best_of=5,
    patience=1.0,
    length_penalty=1.0,
    temperature=(0.0, 0.2, 0.4),
    compression_ratio_threshold=2.4,
    log_prob_threshold=-1.0,
    no_speech_threshold=0.6,
    condition_on_previous_text=False,
    initial_prompt=INITIAL_PROMPT,
    prefix=None,
    suppress_blank=True,
    suppress_tokens=SUPPRESS_TOKENS,
    without_timestamps=False,
    vad_filter=False,
)

def transcribe(audio_int16: np.ndarray) -> str | None:
    # 1. Preprocesar
    audio = preprocess(audio_int16)

    # 2. VAD trim (rechaza si no hay speech)
    trimmed = vad_trim(audio)
    if trimmed is None or len(trimmed) < int(0.3 * 16000):
        return None  # comando ignorado

    duration = len(trimmed) / 16000.0
    kwargs = SHORT_KWARGS if duration < 3.0 else LONG_KWARGS

    # 3. Transcribir
    segments, info = model.transcribe(trimmed, **kwargs)
    segs = list(segments)
    if not segs:
        return None

    # 4. Concatenar texto
    text = " ".join(s.text for s in segs).strip()

    # 5. Quality check
    if not quality_check_all(segs, text, duration):
        return None

    # 6. Post-procesar (strip wake-word residual, normalización)
    text = postprocess_text(text)
    return text

def quality_check_all(segs, text: str, dur: float) -> bool:
    if not text or len(text) < 2:
        return False
    n_words = len(text.split())
    if dur < 0.7 and n_words > 4: return False
    if dur < 1.5 and n_words > 8: return False
    for s in segs:
        if s.avg_logprob is not None and s.avg_logprob < -1.0:
            return False
        if s.no_speech_prob is not None and s.no_speech_prob > 0.6:
            return False
        if s.compression_ratio is not None and s.compression_ratio > 2.4:
            return False
    if is_in_BoH(text):
        return False
    return True

def postprocess_text(text: str) -> str:
    import re
    # Quitar wake-word residual al inicio
    text = re.sub(r"^\s*(hey\s*)?gemma[\s,!.¡]*", "", text, flags=re.IGNORECASE)
    # Strip puntuación inicial sobrante
    text = text.strip(" ,.!?¡¿")
    return text
12.3 Pipeline completo (orden de operaciones)
1. Vosk wake-word detecta "gemma" / "hey gemma" → marca T_end_wake.
2. Acoustic snapshot: extraer del ring buffer audio desde
   T_end_wake (con margen de -50ms) hasta endpoint RMS.
3. (Opcional) cortar el wake-word ANTES de pasar a Whisper.
4. preprocess() - high-pass + normalize ligero
5. vad_trim() - Silero VAD recorta silencio lateral, RECHAZA si no hay speech
6. transcribe() - faster-whisper con kwargs según duración (modo dual)
7. quality_check_all() - heurísticas numéricas + BoH
8. postprocess_text() - cleanup
9. fuzzy_match contra grammar de comandos (si aplica)
10. Pasar al LLM Gemma (en GPU) o ejecutar skill directamente
12.4 Trade-offs y caveats finales

Latencia esperada para comando corto en CPU típica (i7 10ª gen+) con esta config: 300–700 ms transcripción + 20 ms VAD + 5 ms preprocess = ~400–750 ms desde fin del comando hasta texto. Bajo el segundo, alcanzable.
El initial_prompt largo añade 50–100 ms al primer step del decoder (más tokens a procesar en el prompt). Es trade-off aceptable.
El prompt no es robusto: cambios menores cambian resultados. Una vez funcione, fixéalo y no lo toques.
Si los comandos pertenecen a un set cerrado y el LLM Gemma no procesa habla libre, considera seriamente Speech-to-Phrase o Vosk con grammar para los comandos, dejando Whisper solo para "modo dictado / conversación libre". El stack ganaría 5–10× en latencia para skills y 0 alucinaciones.
Whisper siempre alucinará algo de vez en cuando. No hay configuración que lo elimine al 100 %. La capa de quality-check + UX de "perdón, repítelo" es la red de seguridad necesaria.
No actives vad_filter=True con defaults: añade 400+ ms por los speech_pad_ms=400 del faster-whisper. Si lo usas, override defaults a 100 ms y 300 ms (sección 5.5).
No subas a medium en CPU salvo que aceptes 1.5–2 s de latencia. El cuello no es el tamaño del modelo, son las alucinaciones.
Considera GPU si en futuro liberas VRAM: small-int8_float16 en GPU corre a ~50–100 ms y libera CPU para Gemma.

Cierre y resumen accionable
Tu problema actual ("Hey Kema!", "abre estímulo", "Aurestín!") es un caso de manual de alucinaciones de Whisper en clips cortos con vocabulario OOV (anglicismos técnicos) sin biasing. La literatura técnica (paper Whisper original, Careless Whisper Cornell, Calm-Whisper, AGH 2025, OpenAI Cookbook) y los issues principales de GitHub coinciden en que el problema no se resuelve con un solo cambio sino con una combinación de mitigaciones que actúan sobre prompting, decoding, preprocesado y post-procesado.
Las cinco palancas de mayor impacto, en orden de prioridad y derivadas de evidencia documentada:

initial_prompt saturado con "Gemma" y nombres de apps en español natural — la única forma realista en faster-whisper de hacer biasing (no hay shallow fusion real). Resuelve el caso "Hey Kema!" y "abre estímulo".
without_timestamps=False — confirmado empíricamente por Sanchit Gandhi (HuggingFace) y por whisper.cpp/whisper-timestamped issues: forzar al decoder a generar timestamps lo "ancla" temporalmente al audio y reduce divagaciones.
VAD trim previo (Silero v5 con speech_pad_ms=100) que recorta silencio lateral y, sobre todo, rechaza el chunk si no hay speech detectable — corta de raíz alucinaciones de no-speech.
Modo dual: beam_size=1 + temperature=0.0 para comandos cortos, beam_size=5 + temperature tuple para dictado largo. Confirmado por AGH 2501.11378 (Tabla VI) que beam_size=1 tiene menor tasa de alucinaciones en clips cortos.
Quality-check post-transcripción con avg_logprob, compression_ratio, no_speech_prob, word density vs duración, y una Bag of Hallucinations en español. Rechaza el resultado y pide al usuario repetir antes que ejecutar una acción incorrecta.

El modelo small con int8 en CPU x86-64 moderna es la elección correcta: mejor relación coste/calidad/latencia para tu hardware. medium triplica la latencia, los tiny/base degradan accuracy en español, distil-whisper en español no es oficial, y turbo en CPU es más lento que small (encoder pesado).
Si los comandos del asistente forman un conjunto cerrado, considera arquitectónicamente añadir Speech-to-Phrase o Vosk con grammar como capa pre-Whisper: latencia < 200 ms, cero alucinaciones para skills conocidas, y Whisper queda solo para dictado libre y conversación abierta con Gemma. Es la separación que hacen Home Assistant, Rhasspy y OVOS por buenas razones.
Las configuraciones, prompts y bloques de código completos están en la sección 12. Implementadas en conjunto, esperas latencias de comando corto entre 400 y 750 ms en CPU desktop moderna, con la gran mayoría de las alucuinaciones observadas hoy eliminadas, manteniendo accuracy alta en dictado largo. Las invenciones residuales se capturan por la capa de quality-check antes de que lleguen a ejecutar acciones.
Un último apunte: Whisper siempre tendrá una tasa residual de alucinaciones (incluso large-v3 tiene ~1 % según Careless Whisper). La aceptación de esto y el diseño de una red de seguridad ("perdón, no te he entendido, repítelo") es parte de la arquitectura correcta de un asistente; perseguir 0 % al ASR es perseguir una asíntota.