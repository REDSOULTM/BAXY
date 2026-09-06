# Protocolo 10.x — Grok 4.6 High

Revisado 2026-09-04. Los prompts incorporan el
[contrato único de ejecución](00_PROTOCOLO_EJECUCION.md). Ése es el protocolo
vigente: tramos pequeños, estado durable, aceptación reservada, pruebas de
producto y cierre basado en evidencia. Esta ruta se conserva para los enlaces.

Se retiran el reparto 350K+150K y la exigencia de cerrar una campaña en una sola
sesión. Los 500k son capacidad máxima; contexto objetivo 60–100K, corte a 150K.
Un límite medido o FALLO_DE_AMBIENTE no es cumplimiento. High se mantiene.

No cambian Identidad, 200 turnos, N10/M10 (mínimos 1.947/808 + delta), K11
(mínimo 2.036 + delta), cobertura, tres ceros ni Full. Los errores ya vistos en C03
no se resuelven llenando una ventana ni reutilizando holdout como fresco.
Consulta el [lanzador](00_LANZAR_DESDE_10_7.md) para dependencias y la
[revisión](REVISION_SPRINTS_2026-09-04.md) para evidencia y fuentes.
