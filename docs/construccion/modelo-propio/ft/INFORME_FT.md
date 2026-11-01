# Ajuste fino de Qwen3.5-4B y proveedores pendientes: informe final

Producto de partida: `0be0f9de9` (cierre de la auditoría de tus pedidos reales). Producto final: `lote-final3`
`e0a7d9923` con el modelo ajustado **c2-e1.0** (sha256 `8a4b6ce3…`, Q4_K_M, 4B). Aquí sólo hay cifras y descripciones:
tus textos y los datos de entrenamiento viven fuera del repo, en `<evaluacion>\ft_v1`. El detalle de cada paso, con sus
fuentes, está en `PROGRESO.md` («Ajuste fino de Qwen3.5-4B…» y siguientes), y la receta citada en `RECETA.md`.

## Qué se hizo

- **Ajuste fino LoRA** de Qwen3.5-4B en la 4060 Ti, sobre exactamente lo que ve BAXY: las 176 herramientas y el
  prompt de sistema (42.734 tokens, sin recortar), con la misma plantilla y el mismo catálogo. Los datos son tus pedidos
  del conjunto de ajuste, con la respuesta buena del propio modelo como objetivo; ejemplos sintéticos escritos desde el
  catálogo, nunca desde tus frases; y una réplica del latido. Antes de cada ciclo se comparó todo con todos los bancos,
  también los sellados, y se quitó lo que se parecía.
- **8 ciclos y 2 fusiones λ medidos** en los cuatro bancos (decision2, escenas, e2e y falsedades). Cada palanca salió
  de una investigación con fuentes (informes A-D en `<evaluacion>\ft_v1\receta\`).
- **Proveedores y App** (notebook): consola, tope de tiempo del turno, Opera GX, relectura de Word, foco (también con
  la app minimizada), memoria, rutas, la voz desde el primer turno, la App que se cerraba al arrancar, el lanzador que
  reutilizaba binarios viejos, recibos con la ventana que se negó a escribir y **traer una ventana al frente**:
  window.focus y app.open fallaban cuando Windows le negaba el primer plano a BAXY, por ejemplo con una ventana
  invisible de un servicio de juegos delante.

## Qué mejoró (cifras)

| | Base del día (0be0f9de9, modelo base) | Final (e0a7d9923, c2-e1.0) |
|---|---|---|
| e2e de práctica, 3 semillas | 59/90 | **75/90** |
| decision2, media por semilla | 229,33 | 230,00 |
| Escenas del latido, media de 4 pasadas | 31,25 | **32,25**, 0 molestas |
| Falsedades (20 conversaciones, lectura estricta) | 3 | 2 |
| VRAM / RAM del producto | — | 3.901 MiB / 1.787 MiB (≤ 4 GB) |

Por partes: la primera tanda de proveedores, con el modelo base, dejó el e2e igual (19,67 por semilla); con el modelo
ajustado el mismo lote subió a 23,67, y el resto, hasta 25,0, viene de los arreglos posteriores de proveedores y de
la App. En vivo, F1, F2, E001 y W1 salen 3/3.

**Holdout nuevo, medido una vez** (320 casos que nadie de esta sesión vio; la decisión se midió en las dos GPUs y lo
seguro se ejecutó en el notebook con el producto real):

| Pedidos | Holdout de la auditoría (modelo base, 141) | Holdout nuevo (final, 214) |
|---|---|---|
| Bien de punta a punta | 66,0 % | **81,3 %** |
| Eligiendo mal | 14,9 % | **4,7 %** |
| Ejecutando mal | 6,4 % | 14,0 % (unos 25 de 30 por el entorno del notebook: memoria apagada, sin Wi-Fi, sin música, la ventana o el archivo del caso no estaban) |
| Con falsedad, leída a mano | 2,1 % | **0,5 %** (1 clara: dijo «Cerré Paint» y no lo cerró) |

Los dos holdouts no son el mismo banco: el de la auditoría salió de tus pedidos reales y el nuevo lo escribió un
subagente aislado desde el catálogo. Lo que sí es una diferencia medida, en el mismo banco y la misma sesión, es la
decisión: el modelo ajustado acierta 304 de 320 y el base 269 (+35); en pedidos, 205 frente a 182.

## Qué no mejoró

- El latido en el holdout nuevo: 26 de 36 escenas frente a 29 del base, con una molesta más (habla de la salud del
  sistema cuando debía callar). En práctica había subido; en el holdout baja, en una sola pasada.

- Ninguna palanca superó a c2-e1.0 sin bajar un banco. Escalar el adaptador (λ 0,6 y 0,8), LR 5e-5, 2 épocas, datos
  pareados, KL hacia el base, réplica amplia del latido y datos de honestidad sobre los modos: todas bajan el e2e o el
  latido (tabla con fuentes en PROGRESO.md, «Decisión sobre la prórroga»). La prórroga no procedió.
- Cada reentrenamiento perdió algo que c2-e1.0 hace bien en tareas de varios pasos: dar la ruta completa al guardar
  en una subcarpeta y abrir la Calculadora cuando no está. Esas conductas son frágiles entre corridas.

## Cada pendiente del objetivo, medido en el producto final (e0a7d9923 con c2-e1.0)

Medido con el e2e de práctica s0-2 (75/90, escritorio comprobado por semilla) y casos en vivo. El código de cada
arreglo, con archivo:línea, está en PROGRESO.md y en metas.json (`cierre_2026-10-19`).

| Pendiente | Al empezar | Producto final | Estado |
|---|---|---|---|
| Apps de consola, tope del turno | fallaban | arreglados (consola 2/2, cierre del turno a los 90 s) | arreglado |
| Opera GX | cerrar la pestaña fallaba | leer 3/3 y cerrar 3/3, en vivo y en el estado que fallaba | arreglado |
| Relectura de Word | sin leer lo escrito | W1 3/3 en vivo | arreglado |
| Foco (minimizada, otra ventana delante) | fallaba | F1 3/3, F2 3/3; app.open sin quedar detrás en todas las semillas | arreglado |
| memory.recall (todo) | fallaba | contrato y pruebas | arreglado |
| Voz desde el primer turno (E001) | fallaba al arrancar | 3/3 en vivo | arreglado |
| E003, E011, E017, E021, E022, E023, E029 | fallaban | 3/3 | arreglados |
| E019, E024 | fallaban | 2/3 (la semilla que falla es del modelo) | arreglados por mayoría |
| E006, E020 | fallaban | 0/3: el modelo pierde la subcarpeta o busca sin ella | límite del modelo |
| E027 | fallaba | 0/3 en el banco: en dos semillas el modelo se niega («su carpeta privada»); en la otra lo hizo bien y fue el banco el que no vio su respuesta | límite del modelo y fallo del banco |
| E015 | fallaba | 0/3 en el banco: BAXY llega a la biblioteca de Steam, pero el oráculo pide ver 4 títulos y la vista muestra 1-2 | fallo del banco |

## Los tres modos de accesibilidad

- **Normal**: el texto funciona y está listo. La entrada por voz existe pero está en pruebas, y la interfaz lo dice
  («en pruebas · próximamente disponible»).
- **No vidente** y **Movilidad**: no disponibles. La interfaz los ofrecía como perfiles elegibles; ahora dicen
  «próximamente disponible» y no se activan. Lo que existe y lo que falta para ellos está en `MODOS_ACCESIBILIDAD.md`.
- **La mente**: ningún modo cambia lo que ve. Preguntado por esos modos, el modelo final nunca dice «próximamente»
  (0 de 34 en la sonda). Los datos honestos del ciclo 8 lo lograron en 11 de 34, sin mentir más, pero ese ciclo bajó
  el e2e y no se quedó.

## Pendiente

- Que el modelo diga la verdad sobre los modos, y E006, E020 y E027, sin reentrenar (decidiste descartar el
  reentrenamiento por ahora): son las palancas de la meta siguiente, `PROMPT_OBJETIVO_AYUDAS_MODELO.md`. Los arreglos del
  banco para E015 y E027 también van ahí.
- Los grupos que la auditoría dejó como límite.
- La voz para dejar de estar «en pruebas», y el modo No vidente o el de Movilidad: requieren tu decisión.
