# Ajuste fino de Qwen3.5-4B y proveedores pendientes: informe final (2026-10-18)

Producto de partida: `0be0f9de9` (cierre de la auditoría de tus pedidos reales, con la interfaz v4, la voz y la
bandeja). Aquí sólo hay cifras y descripciones; tus textos y los datos de entrenamiento viven fuera del repo, en
`F:\BAXYeval\ft_v1`.

## Qué se hizo

- **Ajuste fino LoRA** de Qwen3.5-4B en la 4060 Ti, con la receta investigada y citada en `RECETA.md`. Entrena sobre
  exactamente lo que ve BAXY: las 176 herramientas y el prompt de sistema (42.734 tokens), la misma plantilla y el mismo
  catálogo. Datos: tus pedidos del conjunto de ajuste (con la respuesta buena del propio modelo como objetivo),
  ejemplos sintéticos escritos desde el catálogo (nunca desde tus frases) y una réplica de su latido. Antes de entrenar,
  todo se comparó con todos los bancos (también los sellados) y se quitó lo parecido.
- **Tres ciclos**: datos de partida, arreglo de datos y ajuste de épocas. El modelo final es el 4B fusionado y
  cuantizado a Q4_K_M con la misma mezcla que el de producción.
- **Proveedores** (notebook): consola, tope de tiempo del turno, Opera GX, relectura de Word, foco y memoria.

## Qué mejoró (bancos de práctica, frente a la base del mismo día)

PENDIENTE: cifras finales del lote (decisión, escenas, e2e, falsedades) y del holdout nuevo.

## Qué no mejoró

PENDIENTE.

## Pendiente

PENDIENTE.
