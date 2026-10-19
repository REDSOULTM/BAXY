# Ajuste fino de Qwen3.5-4B y proveedores pendientes: informe final

Producto de partida: `0be0f9de9` (cierre de la auditoría de tus pedidos reales). Producto final: `lote-final3`
`e0a7d9923` con el modelo ajustado **c2-e1.0** (sha256 `8a4b6ce3…`, Q4_K_M, 4B). Aquí sólo hay cifras y descripciones:
tus textos y los datos de entrenamiento viven fuera del repo, en `F:\BAXYeval\ft_v1`. El detalle de cada paso, con sus
fuentes, está en `PROGRESO.md` («Ajuste fino de Qwen3.5-4B…» y siguientes), y la receta citada en `RECETA.md`.

## Qué se hizo

- **Ajuste fino LoRA** de Qwen3.5-4B en la 4060 Ti, sobre exactamente lo que ve BAXY: las 176 herramientas y el
  prompt de sistema (42.734 tokens, sin recortar), con la misma plantilla y el mismo catálogo. Los datos son tus pedidos
  del conjunto de ajuste, con la respuesta buena del propio modelo como objetivo; ejemplos sintéticos escritos desde el
  catálogo, nunca desde tus frases; y una réplica del latido. Antes de cada ciclo se comparó todo con todos los bancos,
  también los sellados, y se quitó lo que se parecía.
- **8 ciclos y 2 fusiones λ medidos** en los cuatro bancos (decision2, escenas, e2e y falsedades). Cada palanca salió
  de una investigación con fuentes (informes A-D en `F:\BAXYeval\ft_v1\receta\`).
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

**Holdout nuevo, medido una vez** (PENDIENTE: cifras de la fase 4), frente al holdout de la auditoría (66,0 % de
pedidos bien, 14,9 % eligiendo mal, 2,1 % con falsedad).

## Qué no mejoró

- Ninguna palanca superó a c2-e1.0 sin bajar un banco. Escalar el adaptador (λ 0,6 y 0,8), LR 5e-5, 2 épocas, datos
  pareados, KL hacia el base, réplica amplia del latido y datos de honestidad sobre los modos: todas bajan el e2e o el
  latido (tabla con fuentes en PROGRESO.md, «Decisión sobre la prórroga»). La prórroga no procedió.
- Cada reentrenamiento perdió algo que c2-e1.0 hace bien en tareas de varios pasos: dar la ruta completa al guardar
  en una subcarpeta y abrir la Calculadora cuando no está. Esas conductas son frágiles entre corridas.
- Siguen fallando, por el modelo: E006, E015, E020 y E027.

## Los tres modos de accesibilidad

- **Normal**: el texto funciona y está listo. La entrada por voz existe pero está en pruebas, y la interfaz lo dice
  («en pruebas · próximamente disponible»).
- **No vidente** y **Movilidad**: no disponibles. La interfaz los ofrecía como perfiles elegibles; ahora dicen
  «próximamente disponible» y no se activan. Lo que existe y lo que falta para ellos está en `MODOS_ACCESIBILIDAD.md`.
- **La mente**: ningún modo cambia lo que ve. Preguntado por esos modos, el modelo final nunca dice «próximamente»
  (0 de 34 en la sonda). Los datos honestos del ciclo 8 lo lograron en 11 de 34, sin mentir más, pero ese ciclo bajó
  el e2e y no se quedó.

## Pendiente

- Que el modelo diga la verdad sobre los modos sin perder el e2e. El camino medido son datos G9 más rutas; necesita
  un ciclo que no cabía hoy.
- E006, E015, E020 y E027, y los grupos que la auditoría dejó como límite.
- La voz para dejar de estar «en pruebas», y el modo No vidente o el de Movilidad: requieren tu decisión.
