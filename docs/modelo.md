# El modelo de BAXY y su ajuste fino

BAXY piensa con **BAXY-Qwen3.5-4B**, un Qwen3.5-4B con un ajuste fino LoRA propio, fusionado y cuantizado a
Q4_K_M para que quepa en una GPU de 4 GB.

| | |
|---|---|
| Descarga | [huggingface.co/REDSOULTM/BAXY-Qwen3.5-4B-GGUF](https://huggingface.co/REDSOULTM/BAXY-Qwen3.5-4B-GGUF) |
| Fichero | `BAXY-Qwen3.5-4B-c3-Q4_K_M.gguf`, 2.740.937.440 bytes |
| SHA-256 | `485595f734f964b4902028b4a97ef37f31d57d5c651581435917e0043e499f0e` |
| Base | [`Qwen/Qwen3.5-4B`](https://huggingface.co/Qwen/Qwen3.5-4B) (Apache-2.0), cuantización de partida de [`unsloth/Qwen3.5-4B-GGUF`](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF) |
| Servidor | `llama-server` de llama.cpp b11609, con la plantilla Jinja del GGUF y el razonamiento apagado |
| Idiomas | Español e inglés (y su mezcla) |
| Licencia | Apache-2.0, como el modelo base (obra derivada) |

## Qué ve el modelo

En cada turno el modelo recibe el prompt de sistema y **todas** las herramientas del catálogo (más de 180) por
`/v1/chat/completions`, unos 44.000 tokens de prefijo que `llama-server` guarda en caché y en disco. Responde con
llamadas nativas a herramientas; después de cada recibo verificado decide si llama otra o contesta en una frase.

Por eso el ajuste se hace **sobre exactamente lo que ve en producción**: el mismo prefijo, sin recortar
herramientas, la misma plantilla y el mismo catálogo.

## Receta

La receta se investigó con fuentes y se comprobó en una RTX 4060 Ti antes de escalarla. Texto completo, con cada
referencia, en [construccion/modelo-propio/ft/RECETA.md](construccion/modelo-propio/ft/RECETA.md).

- **LoRA en bf16, no QLoRA** (Unsloth desaconseja QLoRA en Qwen3.5).
- **Módulos:** atención (`q,k,v,o_proj`, 8 capas), las 24 capas Gated DeltaNet (`in_proj_qkv`, `in_proj_z`,
  `out_proj`, que la lista habitual de 7 módulos deja fuera) y el MLP (`gate`, `up`, `down_proj`). Nunca visión,
  embeddings ni `lm_head`.
- **Rango 32, α 32**, sin dropout.
- **Pérdida sólo en la respuesta** del asistente.
- **Prefijo real de 42,7k tokens**: el prefijo corre sin gradiente y se reutiliza como caché; cada muestra entrena
  sólo su sufijo. La pérdida coincide con un pase completo dentro del redondeo de bf16.
- **Fusión** sobre los safetensors en el tipo de cada tensor (la fusión estándar de PEFT redondea los float32 de
  DeltaNet), conversión con `convert_hf_to_gguf.py` de b11609 y cuantización Q4_K_M con imatrix.
- **El checkpoint se elige por los bancos, no por la pérdida.**

## Datos

- **Mezcla de partida:** ~60 % llamadas correctas, ~12 % preguntar cuando falta un dato, ~10 % «no lo hago», ~8 %
  charla y texto pegado, ~8 % réplica de las respuestas del propio modelo base para no olvidar.
- **Objetivos on-policy:** la salida del propio modelo que un juez ciego da por buena y que no afirma nada que no
  hizo (rechazo con autodestilación).
- **Sintéticos desde el catálogo**, validados contra el esquema JSON de cada herramienta. Nunca se copian frases de
  los bancos de evaluación.
- **Control de fuga** contra todos los bancos, sellados incluidos: igualdad normalizada, n-gramas de palabras y de
  caracteres, y una pasada semántica con embeddings multilingües.

## Versiones

| Versión | Qué cambió | Resultado principal |
|---|---|---|
| c2 (`c2e1`) | 8 ciclos y 2 fusiones medidos desde el modelo base; queda el ciclo 2 tras una época | e2e de práctica 59/90 → 75/90; en un holdout de 320 casos, decisión 304 frente a 269 del base |
| **c3** (`c3r9b`, semilla A) | LoRA sobre el adaptador de c2, LR 1e-5, una época (361 pasos, lote 16), 5.727 muestras en familias acotadas | Banco amplio de 1.538 pedidos: +23,5 casos (IC 95 % +9,5/+39,2); banco ciego de 160 misiones: 44 frente a 36 logradas |

Lo que enseñó la versión 3:

- **Más datos no fue mejor.** Juntar todas las familias (7.000 a 13.212 muestras) empeoró todos los bancos. Ganó una
  receta pequeña: la base limpia, las salidas buenas del modelo anterior y tres familias acotadas (buscar en la web
  el nombre de una entidad, no aprobar nunca una confirmación ambigua y preguntar cuánto cuando el volumen o el
  brillo se piden sin cantidad).
- **La tasa de aprendizaje manda más que la duración.**
- **Entre dos semillas casi iguales, se eligió la que no mintió**: la semilla B ganaba por poco en el banco amplio, pero
  en una prueba de «Guardar como» dijo haber guardado sin hacerlo; la A dijo la verdad en todas.
- **Dos de cada tres fallos de las pruebas de punta a punta eran de la App, no del modelo**, y se arreglaron en la App.

Costo de la versión 3: **US$237,71** de GPU en la nube (A100). Informe completo en
[construccion/modelo-propio/ft/INFORME_C3.md](construccion/modelo-propio/ft/INFORME_C3.md).

## Replicarlo

Los datos de entrenamiento no se publican porque parten de peticiones reales y de bancos de evaluación privados.
Lo que sí está: la receta, los hiperparámetros, la composición por familias, los controles de fuga y los informes de
cada ronda en [construccion/modelo-propio/ft/](construccion/modelo-propio/ft/), y los bancos y jueces en
`scripts/renew/`. Para un ajuste propio, el camino es: generar sintéticos desde el catálogo
(`src/Baxy.Kernel/Operations/ProductCatalog.cs` y `src/baxy_mind/data/tool_descriptions.en.v1.json`), renderizarlos
con la plantilla del GGUF en `llama-server` (`/apply-template`) y entrenar con la receta de arriba.
