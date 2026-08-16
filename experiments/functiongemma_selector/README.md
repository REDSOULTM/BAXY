# FunctionGemma como selector de hoja de BAXY

Este experimento mide si un modelo pequeño especializado puede resolver la
selección exacta dentro de una familia del catálogo. No reemplaza el router, el
planner ni el LLM conversacional y no tiene autoridad para ejecutar efectos.

La hipótesis de trabajo es una cascada:

1. los reconocedores cerrados conceden solo sus casos inequívocos;
2. el clasificador actual propone una o varias familias;
3. FunctionGemma elige una hoja parametrizada por familia o se abstiene;
4. el planner existente extrae argumentos, conserva dependencias, confirma
   riesgo y verifica cada efecto;
5. el LLM principal sigue formulando todas las respuestas visibles.

Esta separación mantiene al modelo experimental sin autoridad de ejecución y
permite medir exactitud, latencia y VRAM de forma independiente. Ningún asset
se registra en `mind-runtime-v1.json` hasta superar gates congelados, no vistos
y de producto completo.

## Entorno reproducible

El entorno usado en esta campaña vive fuera del repositorio en
`D:\BAXYRuntime\experiments\functiongemma-train-v1`. El checkpoint base vive
fuera de Git y debe coincidir con SHA-256
`af4f8a7c4c5eb82291759fd828720c7bcfcb92a5274556d13dde3caccf5f427b`.

`requirements-lock.txt` documenta las dependencias directas. PyTorch se
instaló desde el índice oficial CUDA 12.8; no se modifica el Python del
producto.

## Prueba de aprendizaje inicial

`build_audio_seed.py` transforma evidencia histórica ya auditada en un corpus
de desarrollo para cinco operaciones de audio. Excluye por texto normalizado
todo el oracle `exact_operation_development.v1.jsonl`. Las etiquetas históricas
de volumen relativo y micrófono se corrigen de forma explícita porque entonces
eran abstenciones por falta de capacidad y hoy existen operaciones reales.

`train_lora.py` entrena solo adaptadores LoRA y enmascara todos los tokens del
prompt: la pérdida se calcula exclusivamente sobre la llamada de selección.
`evaluate_selector.py` evalúa el modelo base o un adaptador sin ejecutar Core.

El oracle de 90 casos es solo desarrollo. Aunque esta prueba alcance 100% en
su porción de audio, no constituye el gate final de 99% ni autoriza promoción.

