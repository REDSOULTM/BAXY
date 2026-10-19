# Ajuste fino de Qwen3.5-4B y proveedores pendientes: informe final

Producto de partida: `0be0f9de9` (cierre de la auditoría de tus pedidos reales, con la interfaz v4, la voz y la
bandeja). Aquí sólo hay cifras y descripciones; tus textos y los datos de entrenamiento viven fuera del repo, en
`F:\BAXYeval\ft_v1`. Detalle de cada paso, con sus fuentes: `PROGRESO.md` («Ajuste fino de Qwen3.5-4B y proveedores
pendientes» y siguientes); receta citada: `RECETA.md`.

## Qué se hizo

- **Ajuste fino LoRA** de Qwen3.5-4B en la 4060 Ti. Entrena sobre exactamente lo que ve BAXY: las 176 herramientas y el
  prompt de sistema (42.734 tokens, sin recortar), la misma plantilla y el mismo catálogo. Datos: tus pedidos del
  conjunto de ajuste (con la respuesta buena del propio modelo como objetivo), ejemplos sintéticos escritos desde el
  catálogo (nunca desde tus frases) y una réplica del latido. Antes de cada ciclo, todo se comparó con todos los bancos,
  también los sellados, y se quitó lo parecido.
- **Ciclos medidos** (PENDIENTE: tabla final). Cada palanca salió de una investigación con fuentes (informes A-D en
  `F:\BAXYeval\ft_v1\receta\`) y se midió en los cuatro bancos.
- **Proveedores y App** (notebook): consola, tope de tiempo del turno, Opera GX, relectura de Word, foco (también con la
  app minimizada), memoria, rutas, la voz desde el primer turno, la App que se cerraba al arrancar y el lanzador que
  reutilizaba binarios viejos.

## Qué mejoró (PENDIENTE: cifras del lote final y del holdout nuevo)

## Qué no mejoró

- Escalar el adaptador hacia el base (λ 0,6 y 0,8), bajar la LR a 5e-5 y entrenar 2 épocas: medidos, ninguno superó a
  c2-e1.0. Los datos pareados v3 subieron la decisión (+5) pero bajaron el latido y el e2e.

## Los tres modos de accesibilidad

- **Normal**: el texto funciona; la entrada por voz existe pero está en pruebas (sólo verificada con grabaciones) y la
  interfaz ahora lo dice («en pruebas · próximamente disponible»).
- **No vidente** y **Movilidad**: no disponibles. La interfaz los ofrecía como perfiles elegibles; ahora dicen
  «próximamente disponible» y no se activan. Inventario de lo que existe y falta para ellos:
  `MODOS_ACCESIBILIDAD.md`.
- **La mente**: ningún modo cambia lo que ve. Antes del ajuste, preguntada por esos modos, BAXY nunca decía
  «próximamente» (0 de 34 en la sonda): PENDIENTE el resultado del ciclo con datos honestos.

## Pendiente

PENDIENTE.
