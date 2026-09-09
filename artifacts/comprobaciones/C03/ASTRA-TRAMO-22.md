# C03 — tramo 22: modelos heredados medidos, ninguno promovido

2026-09-06. EN_CURSO, sin bloqueo externo. El tramo anterior fue progreso:
informe literal y checkpoint actualizados, descarga de base verificada.
Este tramo añade 36 respuestas directas adjudicadas y recupera el GGUF que el
proyecto anterior publicaba. No hay cambios de fuente del producto o del registro.

## Comparación y decisión

Nueve casos congelados: seis preguntas de conocimiento con historial reconstruido
y tres narraciones de hora/audio con hechos verificados de corpus-warm.
Sampler común .7/.8/k20/minp0/seed0, KV q8_0, ngl99, contexto 4096 por slot.
Son diagnósticos directos, no ejecuciones integradas nuevas ni los 100 de aceptación.

| Variante | Evaluación individual | Tiempo total | Pico GPU |
|---|---|---|---|
| Gemma E2B estándar sin QAT | 4/9 aprobados | 10,56 s | 1679,57 MiB |
| Misma base + LoRA d3b0fed4 | 3/9 aprobados | 11,16 s | 1783,57 MiB |
| Base estándar, reasoning nativo | 4/9 aprobados | 41,34 s | 1681,57 MiB |
| GGUF BAXY publicado | 4/9 aprobados | 9,11 s | 1689,57 MiB |

Resultados de revisión manual del asistente, conservadores en idioma y precisión.
Son nueve casos repetidos para comparación; no es porcentaje de completitud C03.
Medición GPU del proceso diagnóstico y sus descendientes, no del producto completo.

El adaptador carga: compatibilidad técnica demostrada, restauración histórica exacta
no demostrada. No arregla spanglish y omite el estado de silencio. Reasoning mejora
la mezcla de idiomas en t10, pero t8/t15 siguen sólo en inglés; t6 usa «muteado» sin
combinar frases de ambos idiomas. No compensa su coste ni pasa el panel.

El GGUF publicado contesta t6 con «Listo, respondo de forma natural en spanglish.»:
no da hora, volumen ni estado. Sus otras preguntas mixtas salen en inglés.
Ninguno se promueve. No repetir variantes de sampler, reasoning o adaptadores para
buscar una corrida favorable. La fidelidad ES/EN de varias lecturas no resuelve C03.

Preguntas, respuestas finales y evaluaciones:
[PRUEBAS_GEMMA_C03.md](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/PRUEBAS_GEMMA_C03.md>).
Cada carpeta tiene PREREG, RESULT, replies y ADJUDICACION; exportación con manifest SHA.

## Procedencia del GGUF publicado recuperado

`../Probando Gemma 4/README.md:223–260` enlaza el artefacto de producción en
[REDSOULTM/baxy-gemma4-E2B-GGUF](https://huggingface.co/REDSOULTM/baxy-gemma4-E2B-GGUF).
Revisión congelada `f9b84ecdcd4ffdc112a5baa21b86d553a9360c71`.
Archivo `gemma-4-E2B-it-Q4_K_M.gguf`, 3427879072 bytes,
SHA256 `9d4a5a653f2733a5faeb5f58a0e30bc064dfd569b0059cabb2547dbc4ba0f4b7`.
Destino `D:/BAXYRuntime/experiments/models/baxy-gemma4-e2b-published-f9b84ecd/`.
DOWNLOAD.json y VERIFIED.json conservan procedencia y validación en streaming.
Descarga sesión60761 terminal0,54,94s. No hace falta volver a descargarlo.

La ficha del autor describe un ajuste de herramientas y respuestas posteriores en
seis idiomas; no acredita conocimientos mejores ni spanglish. No se asumió éxito
a partir de esa ficha. La comparación local anterior contradice que cierre C03.

## Runtime y diagnósticos

- Sesión40492 terminal0: `scratchpad/c03-gemma-inherited-compare.py`, salida ready.
  Primer intento `astra-gemma-inherited-compare` no generó respuestas por usar un
  nombre de argumento incorrecto en el lanzador; se corrigió sólo ese lanzador y
  se preservó el intento fallido. No es un fallo del producto.
- Sesión37148 terminal0: `scratchpad/c03-gemma-reasoning.py`. Reasoning auto,
  presupuesto -1, max_tokens1024,30s por petición. Sin corte forzado de pensamiento.
  Parámetro enable_thinking conforme a la ficha oficial de Google; no se cambió
  el sampler del control. No se publicó su canal de razonamiento como respuesta.
- Sesión59725 terminal0: `scratchpad/c03-published-gemma-probe.py`.
- Sesión90357 terminal0: plantilla del GGUF estándar extraída a
  `scratchpad/c03-gemma-template.jinja`. Líneas179–240 renderizan los mensajes
  system posteriores; no se sostiene la hipótesis de que sólo llegue el primero.
- No quedan modelos/descargas propios de estos ensayos. Registro Granite sin promover.

Referencia primaria del modo de razonamiento:
[Google Gemma E2B](https://huggingface.co/google/gemma-4-E2B-it#2-thinking-mode-configuration).
La advertencia histórica contra cortar pensamiento a mitad está en
`biblioteca/gemma4-agent/documentacion/07_latencia/research/reducir_latencia_thinking_gemma4.md:17`.

## Siguiente vía, acotada por evidencia

El entrenamiento heredado no incluye un grupo etiquetado mixed: conteo en streaming
de `../Probando Gemma 4/dataset_finetune/curated/train_v3.jsonl`:
es3327,en865,otro56,fr662,it647,pt654,de694. Esto no prueba que no haya mezcla en los
textos; sí que el muestreo por idioma no la contempla explícitamente.

`../Probando Gemma 4/dataset_finetune/scripts/train_ft.py:130–180` tiene una herencia
pertinente: entrenamiento con resultados de herramientas y pérdida sólo sobre la
respuesta, enmascarando el resultado para no enseñar a inventarlo. Su configuración
de batch4 midió8,4GB y NO sirve sin cambios aquí. La máquina tiene6GB físicos y el
techo de BAXY sigue4GB. Python del producto es torch2.13.0+cpu; faltan peft,
bitsandbytes,accelerate,datasets,trl. No se tocó ese entorno ni se instaló nada.

Siguiente acción: evaluar un smoke de ajuste de idioma/fidelidad con el mecanismo
heredado de pérdida en respuesta, en entorno separado y sobre el candidato Qwen4B
existente. Antes de entrenar un corpus grande, demostrar viabilidad del perfil de
memoria y separar entrenamiento de validación; no usar los100frescos ni rebautizar
estas preguntas repetidas como aceptación. No iniciar otra colección de modelos.
Si el smoke no cabe, documentar la causa y cambiar el método; no gastar una tanda
entera en instalar un stack incompatible. Aún no se ha probado esa viabilidad.

Pendientes intactos: desarrollo verde,100nuevos adjudicados,UIreal,recuperación final,
runtime registrado reproducible,Fullfinal,publicación propia y contratos posteriores.
