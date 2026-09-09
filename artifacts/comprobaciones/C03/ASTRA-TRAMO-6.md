# C03 — contraste del modelo heredado, 2026-09-06

astra-contextual-guard terminó: 1/3 útil, 2 publicados y 1 fallo de composición.
El guard corrige una salida sin validar, pero no consigue que Granite responda
bien. Seguir sumando vetos sólo desplaza el defecto hacia agotamientos. No se
añadió otro filtro ni se volvió a editar el prompt para perseguir esa muestra.

La siguiente hipótesis usa evidencia previa: Qwen3-8B Q4_K_M heredado obtuvo
10/12 en composición aislada, pero nunca se acreditó en esta entrada completa.
astra-qwen8-product mide seis controles ES/EN/mixed con app, interpretación,
composición, recuperación, voz y Core reales. No es aceptación ni promoción.

Reutiliza ngl20, KV q8_0 y el sampler no-thinking de la prueba previa; coincide
con la recomendación del fabricante:
https://huggingface.co/Qwen/Qwen3-8B#best-practices.
Un sitecustomize sólo de esta prueba aplica ese sampler y registra cada llamada.
No modifica texto, gramática, verificadores, presupuestos ni resultados. El
PYTHONPATH y el modelo se sobreescriben sólo en el entorno hijo del conductor;
el registro de Granite se conserva y se comprueba su hash antes y después.

El monitor hereda ProcessTreeGpuSampler y RamSampler. Atribuye toda la VRAM
al árbol del producto, no al total de nvidia-smi; detiene sólo sus descendientes
si supera 4096 MiB o si la prueba excede 900 s. PREREG.json incluye modelo,
fuente, sampler, corpus y monitor; PROCESS.json guarda los PID; RESULT.json
registrará terminal, VRAM/RAM y conservación del registro. Sin nueva descarga.

Se verificó en el proceso real llama-server el modelo Qwen3-8B, ngl20,
contexto 12288 repartido en tres slots y KV q8_0. sampling.jsonl acredita
temperature 0.7, top_p 0.8, top_k 20, min_p 0 y thinking false. No confundir
la línea informativa Runtime registrado de la consola con el override declarado.
Estado operativo y siguiente paso: CHECKPOINT.md. Full sigue reservado al cierre.

## Proyección y rechazo de prosa válida

Qwen8 integrado: 3/6 útiles, 3335.57 MiB VRAM. El override no se promovió.
La proyección borraba kind y acting. Antes de corregir: seis regresiones
fallan; después, 67 pruebas dueñas pasan. Contraste purpose: 4/6 útiles,
3337.57 MiB VRAM; ADJ y huellas propias. Quedan ambas explicaciones mixed.

Se detecta un falso rechazo independiente: too_many_sentences elimina una
bienvenida válida de tres frases. Se retira el veto general de una sola frase;
se mantienen controles específicos de una pregunta para aclarar/confirmar,
hechos, polaridad y lenguaje. Cuatro ejemplos útiles fallan antes; cuatro
controles de respuestas inválidas ya se rechazan. Tras el cambio: 75 pass en
C03/proyección, voz y primera señal. Prueba integrada sentences preparada,
mismo corpus, modelo y presupuestos; no es una nueva muestra de aceptación.

## Conservar el pedido también al informar progreso

Sentences mantiene 4/6 útiles y recupera ambas bienvenidas ES. ADJ escrita.
No soluciona las explicaciones mixed. El guard de progreso exige palabras
literales desde 44b7c45b (2026-08-23), llm.py 4021–4025; sigue pendiente.

El audit sólo llevaba un estado genérico porque acting reemplazaba el pedido
por JSON. Dos regresiones lo demuestran. Ahora el helper común conserva el
texto de usuario en primer intento y ambos reintentos. Se retira además
la función drop_request_verb: una orden copiada debe reintentarse, no perder
su primer verbo hasta pasar por una respuesta. Pruebas dueñas finales de este
cambio: 222 pass y 101 subtests; ruff verde. Los rechazos de instrucciones,
hechos, polaridad y confirmación se mantienen.

astra-qwen8-request se lanzó prematuramente al aparecer una regresión dueña
que aún exponía omisión de contexto en el segundo intento. Se detuvo sólo
su árbol a los 11.06 s, exit 15, antes de cargar el modelo (0 MiB atribuida).
STOP.json y RESULT.json conservan el aborto: no es una medición de calidad.
Tras corregir y pasar los dueños, se inicia astra-qwen8-request-preserved.
Mismos controles, modelo y presupuestos; añade tiempos de inicio/fin por POST
y requestId al audit diagnóstico. No modifica respuestas ni registro.
