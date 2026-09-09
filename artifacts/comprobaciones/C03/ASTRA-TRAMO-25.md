# C03 — tramo 25: recuperar explicaciones históricas sin heredar su degradación

2026-09-06. EN_CURSO. Tramo anterior: progreso medido de formato y detección de
regresiones; no candidato promovible. No hay bloqueo externo. Full reservado
para conducta final lista. Fuente del producto sin cambios en este tramo.

## Regresión histórica demostrada

Origen: ../Probando Gemma 4/dataset_finetune/curated/train_v3.jsonl,
SHA6ccf110a23090ce274695d24a7c7956f2ea36e91b51fe001509be4a9abd01643.
Su constructor dataset_finetune/scripts/build_v3.py:795–798 reemplaza por un
acuse fijo el correct_reply_style de cualquier fila sin herramientas marcada
reply_is_template, incluso cuando ese campo ya contiene una explicación.

Ejemplo exacto, fila1306: «what's a closure in JavaScript» conserva una explicación
de closure en correct_reply_style, pero final_reply dice «All set.». MVC, TDD y
otras explicaciones sufrieron el mismo reemplazo. Se identificaron37reemplazos
entre filas ES/EN, sin herramientas ni contexto previo, de info/conversacion;
no se afirma que los37 sean errores semánticos sin revisar cada uno.
HISTORICAL_REPLACEMENTS.jsonl conserva entrada, objetivo original y sustituido.
Esto prueba degradación del corpus, no atribuye todos los fallos de los modelos
anteriores a esa sola causa. No se modifica el repositorio de origen.

## Herencia revisada

20conceptos revisados individualmente;60adiciones ES/EN/mixed sobre el contenido
de correct_reply_style. HERITAGE_REVIEW.jsonl conserva fila original y las tres
adaptaciones. Son objetivos revisados/escritos por el asistente, no nuevas
respuestas del modelo ni observaciones del PC. No se copia final_reply a ciegas.
Se matizan definiciones que eran demasiado absolutas, y se excluyen las políticas
antiguas de privacidad, identidad y capacidades no ligadas al catálogo actual.

Contrastes primarios puntuales de contenido:
[closures](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Closures),
[Requests](https://requests.readthedocs.io/en/latest/),
[objetos](https://docs.python.org/3/tutorial/classes.html),
[ADN](https://www.genome.gov/genetics-glossary/Deoxyribonucleic-Acid-DNA).

astra-lora-pilot4-data:192train=132previos+60adiciones;42holdout de desarrollo=
30previos consumidos+12nuevos congelados antes del entrenamiento. No se entrenó
con preguntas ni objetivos de la evaluación. Los100nuevos de aceptación siguen
intactos y pendientes. TRAIN SHAa5d93a84ebbad49c908a37c67d556c7ceeaf3171d4a4af31bc2689be271f76af.
HOLDOUT SHAac66f40ef55e34b16b241bd1055bf64fc36004f540192e8fbc17cf940b07803f.
Mismos hiperparámetros y base inicial; pérdida sólo en respuesta. No se continúa v3.

## Procesos y siguiente acción

Entrenamiento99038 TERMINAL0:385,24s,GPU3027,54MiB,RAM4690,04MiB,
192ejemplos,max417tokens,96actualizaciones. Adaptador safetensors SHA
f03424a802823d804f03af9797a51ecbdd757e4d7f15e2707cc6fec97c706c47.
Conversión22214 TERMINAL0, b9980/c03-pilot-lora-v4-f32.gguf en la base entrenable.
Evaluación64823 TERMINAL0:102respuestas,51casos por brazo v3/v4 mediante
scratchpad/c03-evaluate-lora-pilot4.py. Las regresiones hielo/cifrado son conocidas,
no se presentan como casos frescos. No promover por pérdida ni por memoria.

Preparados24casos de las8rutas/3idiomas en astra-lora-pilot4-routes/CASES.json.
scratchpad/c03-pilot4-route-diagnostic.py --prepare-only no ejecutó inferencia.
Su ejecución queda PAUSADA por petición posterior del dueño: investigar capas primero.
La evaluación v4 queda sin adjudicar con la rúbrica nueva; ningún adaptador promovido.
El diseño previsto llama chat/compose_user_message, sin kernel/providers,
con hechos explícitamente sintéticos. Incluye reintentos reales del compositor,
pero no acredita UI, efectos, recuperación integrada ni aceptación100/100.

Pendientes: desarrollo verde,100normales nuevos/8rutas/3idiomas, recuperación
aparte en misma sesión, UIreal,runtime reproducible registrado,Fullfinal,
publicación validada fuera de main y contratos posteriores afectados hasta12.3.
