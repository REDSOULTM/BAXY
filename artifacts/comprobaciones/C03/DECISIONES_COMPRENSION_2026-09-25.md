# Decisiones tomadas sin el dueño — Fase 3.5b «comprensión natural» (Opus 5.5, 2026-09-25)

Criterio (goal): lo sellado; si no alcanza, la práctica establecida; entre dos, la más reversible y la que nunca afirma
algo que no ocurrió.

## D1. El HEAD de partida es 4f510ee7, no b34c3f39
Situación: al abrir la sesión la rama local estaba en `b34c3f39` y el remoto un commit por delante (`4f510ee7`, sólo
61 líneas de informe en `USO_REAL_2026-09-23.md`, subido por la sesión anterior). Elegido: avance rápido al remoto y
tag `opus-cn-inicio` en `4f510ee7`. El `src`, los `scripts` y las pruebas son byte a byte los de `b34c3f39`.
Revertir: mover el tag.

## D2. La verificación de la sesión anterior sigue y es la base de regresión
Situación: `verify_chain2.sh` (sesión anterior) corría sobre `b34c3f39` con la GPU y, al final, la ventana oficial.
Opciones: pararla y medir la base yo; dejarla terminar. Elegido: dejarla. Mide exactamente el `src` de partida con el
conjunto de regresión que el goal pide (742, capas, reserva MASSIVE, guion del dueño, held-out, cien, tandas); pararla
tiraría horas de GPU y dejaría la verificación de la sesión anterior sin cerrar. Mientras corre: nada de GPU ni de
ventana ni de `src` por mi parte; F1 avanza en CPU (conjuntos, oro, puntuador). Revertir: nada.

## D3. Los conjuntos DEV-A, DEV-B y FINAL viven fuera de git
Situación: los conjuntos mezclan frases públicas y conversaciones escritas por subagentes; la práctica de la campaña
(paso 6, tandas) es no versionarlos. FINAL no se puede abrir hasta el cierre y DEV-B no se mira por fallos.
Elegido: `%LOCALAPPDATA%\BAXY\comprension-2026-09-25\` (dura entre sesiones, fuera del árbol que exploran los
subagentes); en git sólo sus SHA-256 y los scripts que los construyen y puntúan. Revertir: copiarlos al árbol.
