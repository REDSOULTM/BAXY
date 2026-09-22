# Decisiones tomadas sin el dueño — Fase 3.5 (Opus 5.5, 2026-09-22)

Criterio (prompt de la sesión): lo ya sellado en el repositorio; si no alcanza, la práctica establecida; entre dos
iguales, la más fácil de revertir y la que nunca afirma un efecto que no ocurrió.

## 1. El tag `opus55-inicio` no existía
Situación: el prompt dice que el punto de partida está marcado con `opus55-inicio`; no estaba en el repositorio.
Opciones: parar; crearlo en el HEAD de partida. Elegido: crearlo (local) en `b5c9fe72`, el cierre del wall del
notebook que el prompt nombra como punto de partida. No se mueve ni se borra. Revertir: nada que revertir.

## 2. Clases de los turnos del guion del 21 que la tabla no nombra así
Situación: la tabla del 21 usa L/C/A/P/M/K; el prompt pide contexto, guarda, paráfrasis, familia, efecto inventado y
fuera de alcance. Elegido (campo `clase` en `contexto/dueno-2026-09-21.turns.jsonl`, checks intactos):
- «me llegó cortado» (turno 3) cuenta como **guarda**: es un detector que se come la charla, igual que «sin pedido».
- Turno 60 (log 230) salió «no encuentro un pedido» sobre charla: **guarda** (la tabla lo agrupa en la fila C 228–231).
- K (turno 35, el título inventado) y las L de lectura de un pedido (15, 22, 23, 58) cuentan como **paráfrasis**: es la
  vía del modelo (lista corta o elección), que es la clase 3 del prompt.
- 40–41 («no lo hiciste», «dímelo tú») cuentan como **contexto**: reconocer lo que pasó en el turno anterior.
- P del notebook (20, confirmación mal formada) y A/M cuentan como **fuera de alcance**: esperan el límite honesto.
Revertir: el commit del baseline (sólo cambia la etiqueta, no el esperado).
